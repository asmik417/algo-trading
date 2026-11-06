"""Stores what the source pullers return: one insert-only table per source (a re-pull adds only new uids) and a
source_pulls row per (source, day) with its status. Also reads the per-source status for GET /jobs/status.
"""
import json
from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.core.clock import utc_now_iso
from app.engine.data.sources import SOURCES
from app.models import (Announcement, Deal, InsiderTrade, MarketContextRow, NewsItem, QuarterlyResult, Shareholding,
                        SourcePull)


CHUNK = 500


def _row(source: str, r: dict, day: date) -> tuple[type, dict]:
    """(model, column values) for one normalised record."""
    if source == "announcements":
        return Announcement, {"symbol": r["symbol"], "date": r["date"], "at": r.get("at"), "kind": r["kind"][:160],
                              "title": r["title"], "url": r.get("url")}
    if source == "deals":
        return Deal, {k: r.get(k) for k in ("symbol", "date", "kind", "side", "party", "qty", "price")}
    if source == "insider":
        return InsiderTrade, {k: r.get(k) for k in ("symbol", "date", "side", "party", "category", "qty", "value", "price")}
    if source == "shareholding":
        return Shareholding, {k: r.get(k) for k in ("symbol", "kind", "filed_on", "as_of", "promoter_pct", "public_pct",
                                                    "pledge_pct")}
    if source in ("market", "global_cues"):
        return MarketContextRow, {"day": r["date"], "metric": r["key"], "value": r.get("value")}
    if source == "news":
        return NewsItem, {k: r.get(k) for k in ("symbol", "date", "title", "source", "url")}
    if source == "results":
        return QuarterlyResult, {k: r.get(k) for k in ("symbol", "period_end", "filed_on", "nature", "revenue", "ebitda",
                                                       "net_profit", "eps", "margin_pct")}
    raise ValueError(f"unknown source {source}")


def _uid(source: str, r: dict) -> str:
    # market and global cue metrics repeat every day, so the day is part of their identity
    return f"{r['date']}|{r['key']}" if source in ("market", "global_cues") else str(r["key"])[:400]


def persist(db: Session, source: str, day: date, records: list[dict]) -> int:
    """Insert records whose uid is new; returns how many were inserted. Existing rows are never touched."""
    if not records:
        return 0
    dialect = db.get_bind().dialect.name
    insert = pg_insert if dialect == "postgresql" else sqlite_insert
    inserted = 0
    by_model: dict[type, list[dict]] = {}
    for r in records:
        model, values = _row(source, r, day)
        by_model.setdefault(model, []).append({**values, "uid": _uid(source, r), "pulled_day": day.isoformat(),
                                               "data_json": json.dumps(r, ensure_ascii=False)})
    for model, rows in by_model.items():
        for i in range(0, len(rows), CHUNK):  # SQLite allows ~32k bound parameters per statement
            stmt = insert(model).values(rows[i:i + CHUNK]).on_conflict_do_nothing(index_elements=["uid"])
            inserted += db.execute(stmt).rowcount or 0
    db.commit()
    return inserted


def record_pull(db: Session, source: str, day: date, status: str, records: int, inserted: int, error: str | None) -> None:
    """Upsert the (source, day) status: the latest attempt for a day is what the status page shows."""
    row = db.scalar(select(SourcePull).where(SourcePull.source == source, SourcePull.day == day.isoformat()))
    if row is None:
        row = SourcePull(source=source, day=day.isoformat())
        db.add(row)
    row.status, row.records, row.inserted, row.error, row.pulled_at = status, records, inserted, error, utc_now_iso()
    db.commit()


def statuses(db: Session, day: str) -> list[dict]:
    rows = {p.source: p for p in db.scalars(select(SourcePull).where(SourcePull.day == day))}
    return [{"source": s, "day": day, "status": rows[s].status, "records": rows[s].records, "error": rows[s].error}
            for s in SOURCES if s in rows]


def has_rows(db: Session, model: type) -> bool:
    return db.scalar(select(model.id).limit(1)) is not None
