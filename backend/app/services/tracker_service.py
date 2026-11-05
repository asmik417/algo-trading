"""Paper-trading tracker: open positions from suggestions, mark them to market daily, close on stop/target,
flag them due at the planned exit, extend/shorten/close with a logged reason, and per-profile stats.
"""
import math
import threading

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.engine.scoring.engine import evaluate
from app.models import LossReview, Position, PositionEvent, PositionMark, Suggestion
from app.services import analysis_service, market_data, plan_service, profile_service
from app.services.errors import BadInput, Conflict, NotFound

log = get_logger(__name__)

ACTIVE = ("open", "due")
STATUS_FILTERS = ("open", "due", "closed", "all")
CLOSE_REASONS = ("target_hit", "stop_hit", "horizon_closed", "manual")
BENCHMARK_SYMBOL = "NIFTY 50"

# One writer at a time: the daily job and API actions both read-modify-write positions.
_lock = threading.RLock()


# --- helpers ---------------------------------------------------------------------

def _r2(x: float) -> float:
    return round(float(x), 2) + 0.0  # + 0.0 turns -0.0 into 0.0


def _busdays(start: str, end: str) -> int:
    return int(np.busday_count(np.datetime64(start, "D"), np.datetime64(end, "D")))


def _trading_day() -> str:
    day = market_data.panel_day()
    if not day:
        raise Conflict("Market data is not available yet; try again in a minute.")
    return day


def _require_text(value: str | None, what: str) -> str:
    text = (value or "").strip()
    if not text:
        raise BadInput(f"{what} is required.")
    return text


def _event(position: Position, event_type: str, day: str, *, price: float | None = None, reason: str | None = None,
           old_exit: str | None = None, new_exit: str | None = None) -> PositionEvent:
    ev = PositionEvent(event_date=day, event_type=event_type, price=price, reason=reason,
                       old_exit_date=old_exit, new_exit_date=new_exit)
    position.events.append(ev)
    return ev


def _upsert_mark(db: Session, position: Position, day: str, close: float) -> None:
    value = position.qty * close
    pnl = value - position.invested
    db.merge(PositionMark(position_id=position.id, mark_date=day, close=_r2(close), value=_r2(value),
                          pnl=_r2(pnl), pnl_pct=_r2(pnl / position.invested * 100)))
    position.last_mark_date, position.last_close = day, _r2(close)


def _close(db: Session, position: Position, day: str, price: float, reason: str, note: str | None = None) -> None:
    _upsert_mark(db, position, day, price)
    pnl = position.qty * price - position.invested
    position.status, position.closed_on, position.exit_price = "closed", day, _r2(price)
    position.pnl, position.pnl_pct, position.close_reason = _r2(pnl), _r2(pnl / position.invested * 100), reason
    _event(position, "close", day, price=_r2(price), reason=note or reason)


def get_position(db: Session, position_id: int) -> Position:
    p = db.get(Position, position_id)
    if p is None:
        raise NotFound(f"Position {position_id} not found.")
    return p


# --- shaping -----------------------------------------------------------------------

def _has_review(db: Session, position_ids: list[int]) -> set[int]:
    if not position_ids:
        return set()
    return set(db.scalars(select(LossReview.position_id).where(LossReview.position_id.in_(position_ids))))


def to_schema(p: Position, reviewed: bool) -> dict:
    live_value = p.qty * p.last_close if p.last_close is not None else None
    if p.status == "closed":
        pnl, pnl_pct = p.pnl, p.pnl_pct
    elif live_value is not None:
        pnl = _r2(live_value - p.invested)
        pnl_pct = _r2((live_value - p.invested) / p.invested * 100)
    else:
        pnl = pnl_pct = None
    held_until = p.closed_on or p.last_mark_date or p.opened_on
    sug = p.suggestion
    return {
        "id": p.id, "profile_id": p.profile_id, "suggestion_id": p.suggestion_id, "symbol": p.symbol,
        "opened_on": p.opened_on, "entry_price": p.entry_price, "qty": p.qty, "invested": p.invested,
        "capital": p.capital, "cash_left": _r2(p.capital - p.invested),
        "target": p.target, "stop_loss": p.stop_loss,
        "original_exit_date": p.original_exit_date, "planned_exit_date": p.planned_exit_date,
        "status": p.status, "last_mark_date": p.last_mark_date, "last_close": p.last_close,
        "current_value": _r2(live_value) if live_value is not None else None, "pnl": pnl, "pnl_pct": pnl_pct,
        "days_held": _busdays(p.opened_on, held_until),
        "days_to_exit": None if p.status == "closed" else _busdays(p.last_mark_date or p.opened_on, p.planned_exit_date),
        "closed_on": p.closed_on, "exit_price": p.exit_price, "close_reason": p.close_reason,
        "needs_review": p.status == "closed" and (p.pnl or 0) < 0 and not reviewed,
        "stage": sug.stage if sug else None, "signal": sug.signal if sug else None,
    }


def detail(db: Session, position_id: int) -> dict:
    p = get_position(db, position_id)
    out = to_schema(p, bool(_has_review(db, [p.id])))
    marks = db.scalars(select(PositionMark).where(PositionMark.position_id == p.id).order_by(PositionMark.mark_date))
    events = db.scalars(select(PositionEvent).where(PositionEvent.position_id == p.id).order_by(PositionEvent.id))
    out["marks"] = [{"mark_date": m.mark_date, "close": m.close, "value": m.value, "pnl": m.pnl, "pnl_pct": m.pnl_pct}
                    for m in marks]
    out["events"] = [{"id": e.id, "event_date": e.event_date, "event_type": e.event_type,
                      "old_exit_date": e.old_exit_date, "new_exit_date": e.new_exit_date, "reason": e.reason,
                      "price": e.price, "created_at": e.created_at} for e in events]
    out["suggestion"] = (analysis_service.summary(p.suggestion, analysis_service.tracking_lookup(db, p.profile_id))
                         if p.suggestion else None)
    # Same window as the position's own P&L: open day -> last mark (or close), never a live intraday quote.
    change = market_data.nifty_change_pct(p.opened_on, p.closed_on or p.last_mark_date or p.opened_on)
    out["benchmark"] = {"symbol": BENCHMARK_SYMBOL, "change_pct_since_open": change} if change is not None else None
    return out


def list_positions(db: Session, profile_id: int, status: str = "all") -> list[dict]:
    profile_service.get_profile(db, profile_id)
    if status not in STATUS_FILTERS:
        raise BadInput(f"status must be one of {', '.join(STATUS_FILTERS)}.")
    q = select(Position).where(Position.profile_id == profile_id).order_by(Position.id.desc())
    if status != "all":
        q = q.where(Position.status == status)
    rows = list(db.scalars(q))
    reviewed = _has_review(db, [p.id for p in rows])
    return [to_schema(p, p.id in reviewed) for p in rows]


# --- opening -------------------------------------------------------------------------

def _plan_for_bare_symbol(symbol: str, history: pd.DataFrame, params, trading_day: str):
    """Plan for a symbol tracked without a suggestion: stage from price/volume only (no network)."""
    stage = evaluate(symbol, history, {}, [], [], weights=params.weights).stage
    return plan_service.build_plan(history, stage, params, trading_day)


def open_position(db: Session, profile_id: int, suggestion_id: int | None = None, symbol: str | None = None,
                  capital: float | None = None) -> Position:
    profile = profile_service.get_profile(db, profile_id)
    params = profile_service.params_of(profile)
    if suggestion_id is None and not (symbol or "").strip():
        raise BadInput("Give a suggestion_id or a symbol.")
    suggestion = None
    if suggestion_id is not None:
        suggestion = db.get(Suggestion, suggestion_id)
        if suggestion is None:
            raise NotFound(f"Suggestion {suggestion_id} not found.")
        if suggestion.profile_id != profile_id:
            raise BadInput(f"Suggestion {suggestion_id} belongs to another profile.")
        if symbol and symbol.strip().upper() != suggestion.symbol:
            raise BadInput(f"Suggestion {suggestion_id} is for {suggestion.symbol}, not {symbol.strip().upper()}.")
    sym = suggestion.symbol if suggestion else symbol.strip().upper()

    with _lock:
        if db.scalar(select(Position.id).where(Position.profile_id == profile_id, Position.symbol == sym,
                                               Position.status.in_(ACTIVE))) is not None:
            raise Conflict(f"{sym} is already being tracked in this profile.")
        day = _trading_day()
        found = market_data.close_on(sym, day)
        if found is None or found[0] != day:
            raise NotFound(f"No close price for {sym} on {day}.")
        price = found[1]
        capital = float(capital if capital is not None else params.paper_capital)
        qty = math.floor(capital / price)
        if qty < 1:
            raise BadInput(f"Capital {plan_service.rupees(capital)} cannot buy one share of {sym} at "
                           f"{plan_service.rupees(price)}.")
        if suggestion is not None:
            target, stop, exit_date = suggestion.target, suggestion.stop_loss, suggestion.planned_exit_date
        else:
            plan = _plan_for_bare_symbol(sym, market_data.history(sym), params, day)
            if plan is None:
                raise BadInput(f"Not enough price history to plan a trade in {sym}.")
            target, stop, exit_date = plan.target, plan.stop_loss, plan.planned_exit_date

        p = Position(profile_id=profile_id, suggestion_id=suggestion.id if suggestion else None, symbol=sym,
                     opened_on=day, entry_price=_r2(price), qty=qty, invested=_r2(qty * price), capital=_r2(capital),
                     target=target, stop_loss=stop, original_exit_date=exit_date, planned_exit_date=exit_date,
                     status="open")
        db.add(p)
        db.flush()
        _event(p, "open", day, price=_r2(price), new_exit=exit_date)
        _upsert_mark(db, p, day, price)
        db.commit()
        db.refresh(p)
        log.info("Opened position %s: %s x%d @ %s (profile %s)", p.id, sym, qty, price, profile_id)
        return p


# --- daily marking -----------------------------------------------------------------------

# Bhavcopy prices are not adjusted for splits/bonuses/consolidations; a one-day move this large is treated as a
# possible corporate action and auto-close is suspended until the user acts (option (b), approved 2026-11-05).
CORPORATE_ACTION_MOVE = 0.40
CORPORATE_ACTION_PREFIX = "Possible corporate action"
RESUME_EVENTS = ("extend", "shorten")


def corporate_action_note(move_pct: float) -> str:
    return (f"{CORPORATE_ACTION_PREFIX} (split/bonus/consolidation): price moved {move_pct:+.0f}% in one day. "
            "Auto-close suspended; review manually.")


def auto_close_suspended(p: Position) -> bool:
    """True while the newest corporate-action note is newer than the newest extend/shorten event.
    (A manual close also lifts it, by closing the position.) Event order, not date, so acting the same day counts."""
    last_note = last_resume = 0
    for e in p.events:
        if e.event_type == "note" and (e.reason or "").startswith(CORPORATE_ACTION_PREFIX):
            last_note = max(last_note, e.id or 0)
        elif e.event_type in RESUME_EVENTS:
            last_resume = max(last_resume, e.id or 0)
    return last_note > last_resume


def mark_all(db: Session, as_of: str) -> dict:
    """Mark every open/due position for each trading day after its last mark up to `as_of`, closing on
    stop (close <= stop) or target (close >= target) and flagging due at the planned exit. Idempotent.
    A one-day move over 40% vs the previous mark suspends auto-close (see auto_close_suspended)."""
    summary = {"marked": 0, "closed_target": 0, "closed_stop": 0, "marked_due": 0}
    with _lock:
        positions = list(db.scalars(select(Position).where(Position.status.in_(ACTIVE)).order_by(Position.id)))
        for p in positions:
            hist = market_data.history(p.symbol)
            if hist.empty:
                log.warning("Mark: no prices for %s (position %s)", p.symbol, p.id)
                continue
            start = pd.Timestamp(p.last_mark_date or p.opened_on)
            window = hist.loc[(hist.index > start) & (hist.index <= pd.Timestamp(as_of)), "Close"]
            if window.empty:
                continue
            summary["marked"] += 1
            for ts, close in window.items():
                day, close = ts.date().isoformat(), float(close)
                prev = p.last_close
                if prev and abs(close / prev - 1) > CORPORATE_ACTION_MOVE:
                    _event(p, "note", day, price=_r2(close), reason=corporate_action_note((close / prev - 1) * 100))
                    db.flush()  # give the note an id so auto_close_suspended can order it
                    _upsert_mark(db, p, day, close)
                    log.warning("Position %s (%s): %+.0f%% one-day move on %s; auto-close suspended",
                                p.id, p.symbol, (close / prev - 1) * 100, day)
                    continue  # status unchanged on the gap day
                if auto_close_suspended(p):
                    _upsert_mark(db, p, day, close)
                    if p.status == "open" and day >= p.planned_exit_date:
                        p.status = "due"
                        _event(p, "due", day, price=_r2(close), new_exit=p.planned_exit_date)
                        summary["marked_due"] += 1
                    continue
                if p.stop_loss is not None and close <= p.stop_loss:
                    _close(db, p, day, close, "stop_hit", note=f"Stop-loss {plan_service.rupees(p.stop_loss)} hit: "
                                                               f"closed at {plan_service.rupees(close)}.")
                    summary["closed_stop"] += 1
                    break
                if p.target is not None and close >= p.target:
                    _close(db, p, day, close, "target_hit", note=f"Target {plan_service.rupees(p.target)} reached: "
                                                                  f"closed at {plan_service.rupees(close)}.")
                    summary["closed_target"] += 1
                    break
                _upsert_mark(db, p, day, close)
                if p.status == "open" and day >= p.planned_exit_date:
                    p.status = "due"
                    _event(p, "due", day, price=_r2(close), new_exit=p.planned_exit_date)
                    summary["marked_due"] += 1
        db.commit()
    log.info("mark_all(%s): %s", as_of, summary)
    return summary


# --- user actions ------------------------------------------------------------------------

def _active_position(db: Session, position_id: int) -> Position:
    p = get_position(db, position_id)
    if p.status == "closed":
        raise Conflict(f"Position {position_id} is already closed.")
    return p


def extend(db: Session, position_id: int, new_exit_date: str, reason: str) -> Position:
    with _lock:
        p = _active_position(db, position_id)
        reason = _require_text(reason, "A reason for extending")
        if new_exit_date <= p.planned_exit_date:
            raise BadInput(f"New exit date must be after the current planned date {p.planned_exit_date}.")
        _event(p, "extend", _trading_day(), price=p.last_close, reason=reason,
               old_exit=p.planned_exit_date, new_exit=new_exit_date)
        p.planned_exit_date = new_exit_date
        if p.status == "due":
            p.status = "open"
        db.commit()
        return p


def shorten(db: Session, position_id: int, new_exit_date: str, reason: str) -> Position:
    with _lock:
        p = _active_position(db, position_id)
        reason = _require_text(reason, "A reason for shortening")
        if new_exit_date >= p.planned_exit_date:
            raise BadInput(f"New exit date must be before the current planned date {p.planned_exit_date}.")
        if new_exit_date < p.opened_on:
            raise BadInput(f"New exit date cannot be before the position was opened ({p.opened_on}).")
        day = _trading_day()
        _event(p, "shorten", day, price=p.last_close, reason=reason, old_exit=p.planned_exit_date, new_exit=new_exit_date)
        p.planned_exit_date = new_exit_date
        if p.status == "open" and p.last_mark_date and new_exit_date <= p.last_mark_date:
            p.status = "due"
            _event(p, "due", day, price=p.last_close, new_exit=new_exit_date)
        db.commit()
        return p


def close_manual(db: Session, position_id: int, reason: str) -> Position:
    """Close at the latest close. A due position closes as horizon_closed, an open one as manual."""
    with _lock:
        p = _active_position(db, position_id)
        reason = _require_text(reason, "A reason for closing")
        day = _trading_day()
        found = market_data.close_on(p.symbol, day)
        if found is None:
            raise Conflict(f"No close price for {p.symbol} on {day}.")
        _close(db, p, found[0], found[1], "horizon_closed" if p.status == "due" else "manual", note=reason)
        db.commit()
        return p


def add_note(db: Session, position_id: int, note: str) -> Position:
    with _lock:
        p = get_position(db, position_id)
        _event(p, "note", _trading_day(), price=p.last_close, reason=_require_text(note, "Note text"))
        db.commit()
        return p


# --- stats -----------------------------------------------------------------------------------

def _pnl_on_or_before(db: Session, p: Position, day: str) -> float | None:
    return db.scalar(select(PositionMark.pnl).where(PositionMark.position_id == p.id, PositionMark.mark_date <= day)
                     .order_by(PositionMark.mark_date.desc()).limit(1))


def stats(db: Session, profile_id: int) -> dict:
    profile_service.get_profile(db, profile_id)
    rows = list(db.scalars(select(Position).where(Position.profile_id == profile_id)))
    reviewed = _has_review(db, [p.id for p in rows])
    closed = [p for p in rows if p.status == "closed"]
    wins = [p for p in closed if (p.pnl or 0) > 0]
    losses = [p for p in closed if (p.pnl or 0) < 0]
    avg = lambda xs: _r2(sum(xs) / len(xs)) if xs else None  # noqa: E731

    realised = sum(p.pnl or 0 for p in closed)
    unrealised = sum(p.qty * p.last_close - p.invested for p in rows if p.status in ACTIVE and p.last_close is not None)
    closed_by = {r: 0 for r in CLOSE_REASONS}
    for p in closed:
        if p.close_reason in closed_by:
            closed_by[p.close_reason] += 1

    extended_ids = set(db.scalars(select(PositionEvent.position_id).join(Position)
                                  .where(Position.profile_id == profile_id, PositionEvent.event_type == "extend")))
    extended = [p for p in rows if p.id in extended_ids]
    helped = hurt = 0
    for p in extended:
        if p.status != "closed" or p.pnl is None:
            continue
        on_original = _pnl_on_or_before(db, p, p.original_exit_date)
        if on_original is None:
            continue
        helped += p.pnl > on_original
        hurt += p.pnl < on_original

    ranked = sorted(closed, key=lambda p: p.pnl_pct or 0)
    return {
        "open": sum(p.status == "open" for p in rows), "due": sum(p.status == "due" for p in rows),
        "closed": len(closed), "wins": len(wins), "losses": len(losses),
        "win_rate_pct": _r2(len(wins) / len(closed) * 100) if closed else None,
        "avg_pnl_pct": avg([p.pnl_pct for p in closed if p.pnl_pct is not None]),
        "avg_win_pct": avg([p.pnl_pct for p in wins]), "avg_loss_pct": avg([p.pnl_pct for p in losses]),
        "total_pnl": _r2(realised + unrealised), "realised_pnl": _r2(realised), "unrealised_pnl": _r2(unrealised),
        "total_invested": _r2(sum(p.invested for p in rows)),
        "best": {"symbol": ranked[-1].symbol, "pnl_pct": ranked[-1].pnl_pct} if ranked else None,
        "worst": {"symbol": ranked[0].symbol, "pnl_pct": ranked[0].pnl_pct} if ranked else None,
        "closed_by": closed_by,
        "extensions": {"count": len(extended), "helped": int(helped), "hurt": int(hurt)},
        "pending_reviews": sum(1 for p in losses if p.id not in reviewed),
    }
