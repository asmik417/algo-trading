"""SQLite concurrency settings: WAL and busy_timeout are on, and a reader is not blocked by an open writer.
Mirrors Step 6, where a background run writes suggestions while the API serves reads.
"""
import threading

from sqlalchemy import Column, Integer, MetaData, String, Table, insert, select, text

from app.db.session import SessionLocal, engine

_meta = MetaData()
_scratch = Table("concurrency_scratch", _meta, Column("id", Integer, primary_key=True), Column("note", String))


def test_pragmas_are_set():
    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA journal_mode")).scalar().lower() == "wal"
        assert conn.execute(text("PRAGMA busy_timeout")).scalar() == 30000
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_read_while_another_session_writes():
    _meta.create_all(engine)
    writer, reader = SessionLocal(), SessionLocal()
    try:
        writer.execute(insert(_scratch).values(note="committed"))
        writer.commit()

        # Writer holds an open write transaction with an uncommitted row.
        writer.execute(insert(_scratch).values(note="pending"))
        writer.flush()

        # Reader in another thread sees only committed data and is not locked out.
        seen: list[str] = []
        errors: list[Exception] = []

        def read():
            try:
                seen.extend(reader.execute(select(_scratch.c.note)).scalars())
            except Exception as exc:  # pragma: no cover - surfaced by the assert below
                errors.append(exc)

        t = threading.Thread(target=read)
        t.start()
        t.join(timeout=10)
        assert not errors, errors
        assert seen == ["committed"]

        writer.commit()
        reader.rollback()  # end the old read snapshot
        assert sorted(reader.execute(select(_scratch.c.note)).scalars()) == ["committed", "pending"]
    finally:
        writer.close()
        reader.close()
        _meta.drop_all(engine)
