"""The verdict log and scorecard (docs/API_CONTRACT.md -> Verdict log and scorecard): every rules verdict and analyst
view logged once per (symbol, day, source, profile) with that day's close, marked at 20/40/60 sessions, and scored.
"""
import json
from collections import defaultdict

import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models import AppMeta, Suggestion, VerdictLogRow, VerdictMarkRow
from app.services import market_data, profile_service
from app.services.errors import BadInput

log = get_logger(__name__)

HORIZONS = (20, 40, 60)
SIDEWAYS_BAND_PCT = 5.0
RULES_DIRECTION = {"buy": "up", "watch": "sideways", "avoid": "down"}
CURSOR_KEY = "verdict_log_suggestion_cursor"
NO_SIGNAL = "No signal"
WORST = 10


# --- pure scoring rules --------------------------------------------------------------------------------------------------

def is_right(direction: str, change_pct: float) -> bool:
    """up: closed higher; down: closed lower; sideways: within ±5 %."""
    if direction == "up":
        return change_pct > 0
    if direction == "down":
        return change_pct < 0
    return abs(change_pct) <= SIDEWAYS_BAND_PCT


def edge(direction: str, change_pct: float) -> float | None:
    """Change in the direction of the call (up: change, down: -change); None for sideways (no direction)."""
    if direction == "up":
        return change_pct
    if direction == "down":
        return -change_pct
    return None


def row_stats(key: str, verdicts: list[dict], horizon: int) -> dict:
    marked = [(v, m) for v in verdicts for m in v["marks"] if m["sessions"] == horizon]
    right = sum(1 for _, m in marked if m["right"])
    edges = [e for v, m in marked if (e := edge(v["direction"], m["change_pct"])) is not None]
    return {"key": key, "verdicts": len(verdicts), "marked": len(marked), "right": right,
            "hit_rate_pct": round(right / len(marked) * 100, 2) if marked else None,
            "avg_change_pct": round(sum(edges) / len(edges), 2) if edges else None}


def miss_size(v: dict, horizon: int) -> float | None:
    """How badly a marked verdict missed at the horizon (bigger is worse); None when right or not marked."""
    m = next((m for m in v["marks"] if m["sessions"] == horizon), None)
    if m is None or m["right"]:
        return None
    e = edge(v["direction"], m["change_pct"])
    return -e if e is not None else abs(m["change_pct"]) - SIDEWAYS_BAND_PCT


def scorecard_from(verdicts: list[dict], profile_id: int, source: str, horizon: int) -> dict:
    def grouped(key_of) -> list[dict]:
        groups: dict[str, list[dict]] = defaultdict(list)
        for v in verdicts:
            groups[key_of(v)].append(v)
        return [row_stats(k, vs, horizon) for k, vs in sorted(groups.items())]

    worst = sorted((v for v in verdicts if miss_size(v, horizon) is not None),
                   key=lambda v: (-miss_size(v, horizon), v["day"], v["id"]))[:WORST]
    return {"profile_id": profile_id, "source": source, "horizon": horizon,
            "total": row_stats("total", verdicts, horizon),
            "by_source": grouped(lambda v: v["source"]), "by_action": grouped(lambda v: v["action"]),
            "by_signal": grouped(lambda v: v["signal"] or NO_SIGNAL), "by_month": grouped(lambda v: v["day"][:7]),
            "worst": worst}


# --- logging -----------------------------------------------------------------------------------------------------------

def _insert(db: Session, values: dict) -> bool:
    insert = pg_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
    stmt = insert(VerdictLogRow).values(**values).on_conflict_do_nothing(
        index_elements=["symbol", "day", "source", "profile_id"])
    return bool(db.execute(stmt).rowcount)


def _rules_values(row: Suggestion) -> dict | None:
    from app.services import analysis_service  # late import: analysis_service is heavy

    payload = json.loads(row.payload_json or "{}")
    try:
        overall = analysis_service._verdict_of(row, payload)["overall"]
    except Exception:
        log.warning("No verdict for suggestion %s; not logged", row.id, exc_info=True)
        return None
    direction = RULES_DIRECTION[overall]
    level = row.target if direction == "up" else row.stop_loss if direction == "down" else None
    return {"symbol": row.symbol, "day": row.trading_day, "source": "rules", "profile_id": row.profile_id,
            "action": overall, "direction": direction, "level": level, "close": row.price, "signal": row.signal}


def log_rules_verdicts(db: Session) -> int:
    """Log every suggestion saved since the last sweep (runs, watchlist runs, Explore). The first verdict for a
    (symbol, day, profile) wins; later ones that day are not logged again. Returns how many were logged."""
    meta = db.get(AppMeta, CURSOR_KEY)
    cursor = int(meta.value) if meta and meta.value else 0
    rows = list(db.scalars(select(Suggestion).where(Suggestion.id > cursor).order_by(Suggestion.id)))
    logged = 0
    for row in rows:
        values = _rules_values(row)
        if values is not None and _insert(db, values):
            logged += 1
    if rows:
        if meta is None:
            meta = AppMeta(key=CURSOR_KEY)
            db.add(meta)
        meta.value = str(rows[-1].id)
    db.commit()
    return logged


def rules_signal(db: Session, symbol: str, day: str, profile_id: int) -> str | None:
    """The rules signal of the same stock on the same day: this profile's suggestion first, else any profile's."""
    rows = list(db.scalars(select(Suggestion).where(Suggestion.symbol == symbol, Suggestion.trading_day == day)
                           .order_by(Suggestion.id)))
    mine = [r for r in rows if r.profile_id == profile_id]
    return (mine or rows)[0].signal if rows else None


def log_analyst_view(db: Session, view: dict, close: float) -> bool:
    ok = _insert(db, {"symbol": view["symbol"], "day": view["day"], "source": "analyst",
                      "profile_id": view["profile_id"], "action": view["action"], "direction": view["direction"],
                      "level": None, "close": close,
                      "signal": rules_signal(db, view["symbol"], view["day"], view["profile_id"])})
    db.commit()
    return ok


# --- marks ---------------------------------------------------------------------------------------------------------------

def mark_all(db: Session) -> int:
    """Add every 20/40/60-session mark that has come due. Insert-only; returns how many marks were added."""
    have: dict[int, set[int]] = defaultdict(set)
    for vid, sessions in db.execute(select(VerdictMarkRow.verdict_id, VerdictMarkRow.sessions)):
        have[vid].add(sessions)
    pending = [v for v in db.scalars(select(VerdictLogRow)) if len(have[v.id]) < len(HORIZONS)]
    added = 0
    by_symbol: dict[str, list[VerdictLogRow]] = defaultdict(list)
    for v in pending:
        by_symbol[v.symbol].append(v)
    for symbol, verdicts in by_symbol.items():
        hist = market_data.history(symbol)
        if hist.empty:
            continue
        dates = list(hist.index)
        closes = hist["Close"].astype(float).tolist()
        for v in verdicts:
            at = pd.Timestamp(v.day)
            if at not in hist.index:
                continue
            i = dates.index(at)
            for n in HORIZONS:
                if n in have[v.id] or i + n >= len(dates) or not v.close:
                    continue
                change = round((closes[i + n] / v.close - 1) * 100, 2)
                db.add(VerdictMarkRow(verdict_id=v.id, sessions=n, mark_date=dates[i + n].date().isoformat(),
                                      close=round(closes[i + n], 2), change_pct=change, right=is_right(v.direction, change)))
                added += 1
    db.commit()
    return added


# --- reading ---------------------------------------------------------------------------------------------------------------

def _to_schema(v: VerdictLogRow, marks: list[VerdictMarkRow]) -> dict:
    return {"id": v.id, "symbol": v.symbol, "day": v.day, "source": v.source, "profile_id": v.profile_id,
            "action": v.action, "direction": v.direction, "level": v.level, "close": v.close, "signal": v.signal,
            "marks": [{"sessions": m.sessions, "date": m.mark_date, "close": m.close, "change_pct": m.change_pct,
                       "right": m.right} for m in sorted(marks, key=lambda m: m.sessions)]}


def _verdicts(db: Session, profile_id: int, source: str | None = None, symbol: str | None = None,
              limit: int | None = None) -> list[dict]:
    q = select(VerdictLogRow).where(VerdictLogRow.profile_id == profile_id)
    if source in ("rules", "analyst"):
        q = q.where(VerdictLogRow.source == source)
    if symbol:
        q = q.where(VerdictLogRow.symbol == symbol.strip().upper())
    q = q.order_by(VerdictLogRow.day.desc(), VerdictLogRow.id.desc())
    if limit:
        q = q.limit(limit)
    rows = list(db.scalars(q))
    marks: dict[int, list[VerdictMarkRow]] = defaultdict(list)
    if rows:
        for m in db.scalars(select(VerdictMarkRow).where(VerdictMarkRow.verdict_id.in_([r.id for r in rows]))):
            marks[m.verdict_id].append(m)
    return [_to_schema(r, marks[r.id]) for r in rows]


def _profile_id(db: Session, profile_id: int | None) -> int:
    return profile_service.get_profile(db, profile_id).id if profile_id else profile_service.get_active(db).id


def scorecard(db: Session, profile_id: int | None = None, source: str = "both", horizon: int = 20) -> dict:
    if source not in ("rules", "analyst", "both"):
        raise BadInput("source must be rules, analyst or both.")
    if horizon not in HORIZONS:
        raise BadInput("horizon must be 20, 40 or 60.")
    pid = _profile_id(db, profile_id)
    log_rules_verdicts(db)   # cheap: only suggestions saved since the last sweep
    return scorecard_from(_verdicts(db, pid, source), pid, source, horizon)


def verdicts(db: Session, profile_id: int | None = None, symbol: str | None = None, limit: int = 50) -> list[dict]:
    pid = _profile_id(db, profile_id)
    log_rules_verdicts(db)
    return _verdicts(db, pid, symbol=symbol, limit=limit)
