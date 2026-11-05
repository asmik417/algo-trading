"""Database engine, session factory, the FastAPI `get_db` dependency and `init_db()`.
SQLite by default (file under backend/data/); switch to Postgres by setting DATABASE_URL.
"""
import os
from collections.abc import Iterator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.base import Base

_url = make_url(settings.DATABASE_URL)
_is_sqlite = _url.get_backend_name() == "sqlite"

if _is_sqlite and _url.database and _url.database != ":memory:":
    os.makedirs(os.path.dirname(os.path.abspath(_url.database)), exist_ok=True)

# Background run threads and the scheduler share the engine, so SQLite must allow cross-thread use.
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
)

if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record):
        # foreign_keys: cascade deletes. WAL + busy_timeout: a background run thread can
        # write suggestions while API threads read, without "database is locked".
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=30000")
        cur.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _upgrade_suggestions_table() -> None:
    """2026-11-05: suggestions gained `source` and a nullable run_id/rank. create_all cannot alter
    an existing table, so an old-shape table is rebuilt — only while it is still empty."""
    insp = inspect(engine)
    if "suggestions" not in insp.get_table_names():
        return
    if "source" in {c["name"] for c in insp.get_columns("suggestions")}:
        return
    with engine.begin() as conn:
        rows = conn.execute(text("SELECT COUNT(*) FROM suggestions")).scalar()
        if rows:
            raise RuntimeError("suggestions table has the old shape and holds data; migrate it by hand")
        conn.execute(text("DROP TABLE suggestions"))


# Columns added to existing tables after they first shipped: table -> {column: SQL type + default}.
# Added in place (data kept), since create_all never alters an existing table.
_ADDED_COLUMNS = {
    "suggestion_runs": {  # 2026-11-05: watchlist runs
        "kind": "VARCHAR(16) NOT NULL DEFAULT 'full'",
        "symbols_json": "TEXT",
        "item_errors_json": "TEXT",
    },
}


def _add_missing_columns() -> None:
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    with engine.begin() as conn:
        for table, columns in _ADDED_COLUMNS.items():
            if table not in tables:
                continue  # create_all builds it with every column
            have = {c["name"] for c in insp.get_columns(table)}
            for name, ddl in columns.items():
                if name not in have:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def init_db() -> None:
    import app.models  # noqa: F401  (registers every table on Base.metadata)

    _upgrade_suggestions_table()
    _add_missing_columns()
    Base.metadata.create_all(bind=engine)
