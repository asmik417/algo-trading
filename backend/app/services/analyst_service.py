"""The analyst view (docs/API_CONTRACT.md -> Analyst view): Claude's opinion on one stock for one day and one strategy,
from the evidence pack plus that strategy's own rules verdict, audited for numbers, cached per (symbol, day, profile).
"""
import json
import threading
from datetime import date

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import utc_now_iso
from app.core.logging import get_logger
from app.core.redaction import redact
from app.db.session import SessionLocal
from app.engine.agents import analyst_agent
from app.engine.agents.number_audit import unsupported_numbers
from app.engine.data.sources import common
from app.models import AnalystViewRow, MarketBriefRow, Position
from app.services import evidence_service, market_data, profile_service, scorecard_service, source_service
from app.services.errors import NotFound

log = get_logger(__name__)

MIN_HEADLINES = 3          # fewer than this in the pack (latest day only): search the web for the stock's news
HORIZON = 20
AGREES = {"buy": {"buy", "add"}, "watch": {"watch", "hold"}, "avoid": {"avoid", "exit", "trim"}}

_lock = threading.Lock()
_in_flight: set[tuple[str, str, int]] = set()
_failures: dict[tuple[str, str, int], str] = {}


def agrees_with_rules(action: str, rules_overall: str | None) -> bool | None:
    """buy↔buy/add, watch↔watch/hold, avoid↔avoid/exit/trim; None when there is no rules verdict."""
    if rules_overall is None:
        return None
    return action in AGREES.get(rules_overall, set())


# --- the evidence the model sees --------------------------------------------------------------------------------------

def _pct(a: float | None, b: float | None) -> float | None:
    return round((a / b - 1) * 100, 2) if a is not None and b else None


def derived(pack: dict, plan: dict | None, position: Position | None) -> dict:
    """Figures computed by code so the model never has to: year-on-year and quarter-on-quarter changes, the close
    against the plan's levels and, for a holding, its return so far."""
    out: dict = {}
    q = pack.get("quarters") or []
    if q:
        latest = q[0]
        year_ago = next((r for r in q[1:] if r["period"][5:] == latest["period"][5:]
                         and int(r["period"][:4]) == int(latest["period"][:4]) - 1), None)
        prev = q[1] if len(q) > 1 else None
        for field in ("revenue", "ebitda", "net_profit"):
            if year_ago and year_ago[field] is not None and year_ago[field] > 0:
                out[f"latest_quarter_{field}_yoy_pct"] = _pct(latest[field], year_ago[field])
            if prev and prev[field] is not None and prev[field] > 0:
                out[f"latest_quarter_{field}_qoq_pct"] = _pct(latest[field], prev[field])
        if year_ago and latest["margin_pct"] is not None and year_ago["margin_pct"] is not None:
            out["latest_quarter_margin_change_pts_yoy"] = round(latest["margin_pct"] - year_ago["margin_pct"], 2)
    close = (pack.get("price") or {}).get("close")
    if plan and close:
        out["close_vs_entry_optimal_pct"] = _pct(close, plan.get("entry_optimal"))   # + means above the entry
        out["upside_to_target_pct"] = _pct(plan.get("target"), close)
        out["downside_to_stop_pct"] = _pct(plan.get("stop_loss"), close)            # negative: the drop to the stop
    if position is not None and close:
        out["holding"] = {"opened_on": position.opened_on, "entry_price": position.entry_price,
                          "return_pct": _pct(close, position.entry_price), "target": position.target,
                          "stop_loss": position.stop_loss, "planned_exit_date": position.planned_exit_date}
    return {k: v for k, v in out.items() if v is not None}


def _without_urls(x):
    """URLs are full of digits that are not evidence; the model never needs them."""
    if isinstance(x, dict):
        return {k: _without_urls(v) for k, v in x.items() if k != "url"}
    if isinstance(x, list):
        return [_without_urls(v) for v in x]
    return x


def _position(db: Session, symbol: str, profile_id: int) -> Position | None:
    return db.scalar(select(Position).where(Position.symbol == symbol, Position.profile_id == profile_id,
                                            Position.status.in_(("open", "due"))).order_by(Position.id.desc()))


def _add_web_headlines(db: Session, symbol: str, day: str, pack: dict, usage: dict, notes: list[str]) -> dict:
    """Latest day only: when the pack has few headlines, one news search for the stock; results are stored as news
    and appended to the pack's headlines (and the stored pack) before reasoning."""
    if day != market_data.panel_day() or len(pack["headlines"]) >= MIN_HEADLINES:
        return pack
    names = {s: n for n, s in common.known_names().items()}
    found, search_usage, error = analyst_agent.search_news(symbol, (names.get(symbol) or symbol).title(),
                                                           date.fromisoformat(day))
    for k, v in search_usage.items():
        usage[k] += v
    if error:
        notes.append(f"news search: {error}")
        return pack
    titles = {h["title"] for h in pack["headlines"]}
    new = [h for h in found if h["title"] not in titles]
    if not new:
        return pack
    source_service.persist(db, "news", date.fromisoformat(day),
                           [{**h, "key": f"{symbol}:{h['url']}", "symbol": symbol} for h in new])
    pack = {**pack, "headlines": pack["headlines"] + [{k: h[k] for k in ("date", "title", "source", "url")} for h in new],
            "unavailable": [u for u in pack["unavailable"] if u != "headlines"]}
    evidence_service.save(db, pack)
    return pack


# --- build -------------------------------------------------------------------------------------------------------------

def _to_schema(row: AnalystViewRow) -> dict:
    return {**json.loads(row.view_json), "id": row.id, "created_at": row.created_at}


def view_for(db: Session, symbol: str, day: str, profile_id: int) -> dict | None:
    row = db.scalar(select(AnalystViewRow).where(AnalystViewRow.symbol == symbol.upper(), AnalystViewRow.day == day,
                                                 AnalystViewRow.profile_id == profile_id))
    return _to_schema(row) if row else None


def analyze(db: Session, symbol: str, day: str, profile_id: int) -> dict:
    """Build, store, log and return the view (or return the cached one). Raises NotFound when the stock has no
    price on `day`, RuntimeError when the model gave no usable answer (nothing is stored then)."""
    sym = symbol.strip().upper()
    cached = view_for(db, sym, day, profile_id)
    if cached:
        return cached
    profile = profile_service.get_profile(db, profile_id)
    try:
        pack = evidence_service.get(db, sym, date.fromisoformat(day))
    except NotFound:
        pack = evidence_service.build(db, sym, day, fetch_missing=True)
    hist = market_data.history(sym)
    hist = hist.loc[hist.index <= pd.Timestamp(day)]
    verdict, plan, _ = evidence_service.rules_section(db, sym, day, hist, profile)   # this strategy's own call
    position = _position(db, sym, profile.id)
    usage, notes = analyst_agent.empty_usage(), []
    pack = _add_web_headlines(db, sym, day, pack, usage, notes)
    regime = db.scalar(select(MarketBriefRow.brief_json).where(MarketBriefRow.day == day))
    evidence = _without_urls({
        **pack, "rules_verdict": verdict, "plan": plan, "strategy": profile.name,
        "is_holding": position is not None, "market_regime": json.loads(regime)["regime"] if regime else None,
        "derived": derived(pack, plan, position)})
    if verdict is None:
        evidence["unavailable"] = sorted(set(evidence["unavailable"]) | {"rules_verdict"})
    actions = analyst_agent.HOLDING_ACTIONS if position is not None else analyst_agent.NEW_ACTIONS

    data, u, error, model = analyst_agent.reason(evidence, actions)
    for k, v in u.items():
        usage[k] += v
    if data is None:
        raise RuntimeError(f"analyst gave no answer: {error}")
    audited = True
    bad = unsupported_numbers(analyst_agent.texts_of(data), evidence, extra=analyst_agent.FIXED_NUMBERS)
    if bad:
        notes.append("first answer used numbers not in the evidence: " + ", ".join(bad))
        retry, u, error, model2 = analyst_agent.reason(evidence, actions, data, bad)
        for k, v in u.items():
            usage[k] += v
        if retry is None:
            notes.append(f"retry gave no answer ({error}); the first answer is kept")
            audited = False
        else:
            data, model = retry, model2
            bad = unsupported_numbers(analyst_agent.texts_of(data), evidence, extra=analyst_agent.FIXED_NUMBERS)
            if bad:
                notes.append("second answer still used numbers not in the evidence: " + ", ".join(bad))
                audited = False
    view = {"symbol": sym, "day": day, "profile_id": profile.id,
            "observations": data["observations"], "anomalies": data["anomalies"], "bull_case": data["bull_case"],
            "bear_case": data["bear_case"], "tests": data["tests"], "action": data["action"],
            "direction": data["direction"], "horizon_sessions": HORIZON, "confidence": data["confidence"],
            "trigger": data["trigger"], "want_to_know": data["want_to_know"],
            "agrees_with_rules": agrees_with_rules(data["action"], verdict["overall"] if verdict else None),
            "audited": audited, "audit_notes": notes, "model": model}
    row = AnalystViewRow(symbol=sym, day=day, profile_id=profile.id, view_json=json.dumps(view, ensure_ascii=False),
                         audited=audited, model=model, evidence_json=json.dumps(evidence, ensure_ascii=False),
                         usage_json=json.dumps(usage), cost_usd=analyst_agent.cost_usd(usage, model),
                         created_at=utc_now_iso())
    db.add(row)
    db.commit()
    scorecard_service.log_analyst_view(db, view, float(hist["Close"].iloc[-1]))
    log.info("Analyst view %s %s profile %s: %s/%s, audited=%s, $%s", sym, day, profile.id, view["action"],
             view["confidence"], audited, row.cost_usd)
    return _to_schema(row)


# --- queueing (POST) and reading (GET) -----------------------------------------------------------------------------------

def _run_queued(key: tuple[str, str, int]) -> None:
    try:
        with SessionLocal() as db:
            analyze(db, *key)
        _failures.pop(key, None)
    except Exception as e:
        log.warning("Analyst view %s failed: %s", key, e)
        _failures[key] = redact(str(e) or type(e).__name__)[:300]
    finally:
        with _lock:
            _in_flight.discard(key)


def request(db: Session, symbol: str, profile_id: int) -> tuple[dict, bool]:
    """POST: (body, ready). The cached view for the latest day when there is one, else queue it."""
    profile = profile_service.get_profile(db, profile_id)
    day = market_data.panel_day()
    if not day:
        raise NotFound("Market data is not available yet.")
    sym = symbol.strip().upper()
    hist = market_data.history(sym)
    if hist.empty or hist.index[-1] != pd.Timestamp(day):
        raise NotFound(f"{sym} did not trade on {day}.")
    existing = view_for(db, sym, day, profile.id)
    if existing:
        return existing, True
    key = (sym, day, profile.id)
    with _lock:
        if key not in _in_flight:
            _in_flight.add(key)
            _failures.pop(key, None)
            threading.Thread(target=_run_queued, args=(key,), name=f"analyst-{sym}", daemon=True).start()
    return {"status": "queued"}, False


def get(db: Session, symbol: str, day: date | None, profile_id: int | None) -> dict:
    pid = profile_service.get_profile(db, profile_id).id if profile_id else profile_service.get_active(db).id
    sym = symbol.strip().upper()
    q = select(AnalystViewRow).where(AnalystViewRow.symbol == sym, AnalystViewRow.profile_id == pid)
    q = q.where(AnalystViewRow.day == day.isoformat()) if day else q.order_by(AnalystViewRow.day.desc())
    row = db.scalar(q.limit(1))
    if row is None:
        failure = next((why for (s, d, p), why in _failures.items()
                        if s == sym and p == pid and (day is None or d == day.isoformat())), None)
        raise NotFound(f"No analyst view for {sym}" + (f": the last attempt failed ({failure})." if failure else "."))
    return _to_schema(row)


def cost_of(db: Session, view_id: int) -> tuple[float | None, dict]:
    row = db.get(AnalystViewRow, view_id)
    return (row.cost_usd, json.loads(row.usage_json)) if row else (None, {})
