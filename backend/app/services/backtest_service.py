"""Backtests: validate and queue, run one at a time in a background thread (history -> fundamentals -> scanning ->
simulating -> saving), persist trades and results, and assemble the results view. Scoring reuses the full-run
pipeline (suggestion_service / plan_service) through app/engine/backtest; nothing is scored differently here.
"""
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from functools import partial

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import utc_now_iso
from app.core.logging import get_logger
from app.core.redaction import redact
from app.db.session import SessionLocal
from app.engine.backtest import calendar, fundamentals, patterns, replay, simulate, stats
from app.engine.data import fetcher
from app.engine.params import ScreenParams
from app.engine.scoring import market_regime
from app.models import Backtest, BacktestTrade
from app.services import market_data, plan_service, profile_service, review_service, suggestion_service
from app.services.errors import BadInput, Conflict, NotFound

log = get_logger(__name__)

HISTORY_MARGIN_DAYS = 420     # calendar days fetched before the requested start (250 trading days + slack)
MAX_RANGE_YEARS = 3
FETCH_WORKERS = 3   # bulk fetches also go through fetcher.BULK_LIMITER to stay under Yahoo's rate limit
ACTIVE = ("queued", "running")

_lock = threading.Lock()                 # guards _progress and the one-backtest-at-a-time check
_progress: dict[int, dict] = {}


# --- progress ----------------------------------------------------------------------------------------

def _set_progress(bt_id: int, **fields) -> None:
    with _lock:
        _progress.setdefault(bt_id, {"phase": "history", "done": 0, "total": 0, "current_symbol": None}).update(fields)


def progress_of(bt: Backtest) -> dict:
    with _lock:
        live = _progress.get(bt.id)
        if live is not None:
            return dict(live)
    n = bt.scan_count or 0
    if bt.status == "done":
        return {"phase": "done", "done": n, "total": n, "current_symbol": None}
    if bt.status == "failed":
        return {"phase": "done", "done": 0, "total": n, "current_symbol": None}
    return {"phase": "history", "done": 0, "total": 0, "current_symbol": None}


# --- create / validate ------------------------------------------------------------------------------------

def _parse_day(value, field: str) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        raise BadInput(f"{field} must be a date like 2026-01-31.") from None


def initial_caveats(mode: str) -> list[str]:
    return list(fundamentals.CAVEATS[mode]) + list(fundamentals.CAVEATS["common"])


def _spawn(bt_id: int) -> None:
    threading.Thread(target=execute, args=(bt_id,), name=f"backtest-{bt_id}", daemon=True).start()


def create(db: Session, profile_id: int, start_date, end_date, frequency: str = "weekly",
           entry_rule: str = "next_close", fundamentals_mode: str = "point_in_time", cost_pct: float = 0.3,
           capital_per_trade: float | None = None) -> Backtest:
    profile = profile_service.get_profile(db, profile_id)
    params = profile_service.params_of(profile)
    start, end = _parse_day(start_date, "start_date"), _parse_day(end_date, "end_date")
    last_day = market_data.panel_day()
    if start >= end:
        raise BadInput("start_date must be before end_date.")
    if last_day and end > date.fromisoformat(last_day):
        raise BadInput(f"end_date must be on or before the last trading day, {last_day}.")
    if (pd.Timestamp(start) + pd.DateOffset(years=MAX_RANGE_YEARS)).date() < end:
        raise BadInput(f"A backtest can cover at most {MAX_RANGE_YEARS} years.")
    if not 0 <= cost_pct <= 5:
        raise BadInput("cost_pct must be between 0 and 5.")
    capital = float(capital_per_trade if capital_per_trade is not None else params.paper_capital)
    if capital <= 0:
        raise BadInput("capital_per_trade must be positive.")

    with _lock:  # check-and-insert as one step, so two requests cannot both start
        busy = db.scalar(select(Backtest).where(Backtest.status.in_(ACTIVE)).order_by(Backtest.id).limit(1))
        if busy is not None:
            raise Conflict("A backtest is already running", backtest_id=busy.id)
        bt = Backtest(profile_id=profile.id, status="queued", start_date=start.isoformat(), end_date=end.isoformat(),
                      frequency=frequency, entry_rule=entry_rule, fundamentals_mode=fundamentals_mode,
                      cost_pct=float(cost_pct), capital_per_trade=capital, params_json=profile.params_json,
                      caveats_json=json.dumps(initial_caveats(fundamentals_mode)))
        db.add(bt)
        db.commit()
        _progress[bt.id] = {"phase": "history", "done": 0, "total": 0, "current_symbol": None}
    _spawn(bt.id)
    return bt


# --- execution ------------------------------------------------------------------------------------------------

def _trading_days(histories: dict[str, pd.DataFrame]) -> list[pd.Timestamp]:
    if not histories:
        return []
    return list(pd.DatetimeIndex(np.unique(np.concatenate([h.index.values for h in histories.values()]))))


def _scan_params(bt: Backtest) -> tuple[ScreenParams, bool]:
    """(params the scans run with, require_fundamentals). technical_only rewrites the pillar weights."""
    params = ScreenParams.from_json(bt.params_json)
    if bt.fundamentals_mode != "technical_only":
        return params, True
    values = params.to_dict()
    for pillar, weight in fundamentals.technical_only_weights(params.weights).items():
        values[f"w_{pillar}"] = weight
    return ScreenParams(values=values), False


def execute(bt_id: int) -> None:
    with SessionLocal() as db:
        bt = db.get(Backtest, bt_id)
        try:
            bt.status, bt.started_at = "running", utc_now_iso()
            db.commit()
            caveats = json.loads(bt.caveats_json)
            params, require_fundamentals = _scan_params(bt)
            start, end = date.fromisoformat(bt.start_date), date.fromisoformat(bt.end_date)

            # 1. history: bhavcopy days for the range plus the warm-up, downloaded once and cached.
            _set_progress(bt_id, phase="history", done=0, total=0)
            histories = market_data.histories_for_range(start - timedelta(days=HISTORY_MARGIN_DAYS), end)
            effective_start, scans = calendar.scan_dates(_trading_days(histories), start, end, bt.frequency)
            if not scans:
                raise RuntimeError("Not enough price history for a single scan date in this range.")
            if effective_start > start:
                caveats.append(f"Start moved from {start.isoformat()} to {effective_start.isoformat()} so that 250 "
                               "trading days of history precede the first scan.")
            bt.start_date, bt.scan_count = effective_start.isoformat(), len(scans)
            db.commit()

            # 2. fundamentals: shortlist every scan date (cheap), fetching each new symbol's bundle once.
            today_day = market_data.panel_day()
            bundles: dict[str, dict] = {}
            shortlists: dict[pd.Timestamp, list[str]] = {}
            with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
                for i, scan in enumerate(scans, start=1):
                    _set_progress(bt_id, phase="fundamentals", done=i - 1, total=len(scans),
                                  current_symbol=scan.date().isoformat())
                    shortlists[scan] = replay.shortlist(scan, histories, params, suggestion_service.prefilter)
                    if require_fundamentals:
                        new = [s for s in shortlists[scan] if s not in bundles]
                        fetch = partial(suggestion_service.load_fundamentals, today_day, limiter=fetcher.BULK_LIMITER)
                        for sym, bundle in zip(new, pool.map(fetch, new)):
                            bundles[sym] = bundle
            if require_fundamentals:
                missing = sum(1 for b in bundles.values() if not suggestion_service.has_info(b))
                caveats.append(f"{missing} of {len(bundles)} shortlisted stocks had no fundamentals (Yahoo returned "
                               "nothing for them, even after retries), so they could not be scored.")
            today_close = {sym: market_data.latest_close(sym) for sym in bundles}

            def bundle_for(sym: str, day: pd.Timestamp, cut: pd.DataFrame) -> dict:
                if not require_fundamentals:
                    return fundamentals.technical_only_bundle()
                return fundamentals.point_in_time_bundle(bundles.get(sym, {}), day, float(cut["Close"].iloc[-1]),
                                                         today_close.get(sym), cut)

            # 3. scanning: the full-run pipeline on histories cut at each scan date. Nifty (for the market filter and
            #    the trade comparison) is fetched with the same warm-up as prices; each scan only sees Nifty up to it.
            nifty = market_data.nifty_closes_range(start - timedelta(days=HISTORY_MARGIN_DAYS), end)
            if nifty is None:
                caveats.append("Nifty 50 history was unavailable, so trade-vs-Nifty figures are empty"
                               + (" and the market filter was skipped." if params.min_nifty_vs_ema50_pct > 0 else "."))
            all_picks: list[replay.Pick] = []
            for i, scan in enumerate(scans, start=1):
                _set_progress(bt_id, phase="scanning", done=i - 1, total=len(scans), current_symbol=scan.date().isoformat())
                market = ({"nifty_vs_ema50_pct": market_regime.nifty_vs_ema50_pct(nifty, scan)}
                          if params.min_nifty_vs_ema50_pct > 0 else {})
                score = partial(suggestion_service.score_symbol, require_fundamentals=require_fundamentals, market=market)
                all_picks += replay.picks(scan, histories, shortlists[scan], params, score=score,
                                          plan=plan_service.build_plan, bundle_for=bundle_for,
                                          max_suggestions=int(params.max_suggestions))

            # 4. simulating: walk every pick forward with the Tracker's rules, then tag the losers.
            _set_progress(bt_id, phase="simulating", done=len(scans), total=len(scans), current_symbol=None)
            sim = simulate.simulate_all(all_picks, histories, end, bt.entry_rule, bt.cost_pct, bt.capital_per_trade, nifty)
            patterns.tag_losses(sim.trades, histories)
            if sim.dropped_corporate_action:
                caveats.append(f"{sim.dropped_corporate_action} trade(s) left out: a one-day move over 40% while held "
                               "looks like an unadjusted split or bonus, so their P&L would be fiction.")

            # 5. saving
            _set_progress(bt_id, phase="saving")
            summary = stats.summary(sim.trades, sim.skipped_repeat, sim.skipped_no_fill, bt.capital_per_trade)
            results = stats.breakdowns(sim.trades)
            results["loss_patterns"] = stats.loss_patterns(sim.trades, review_service.TAGS)
            results["equity_curve"] = stats.equity_curve(sim.trades)
            db.add_all(_trade_row(bt_id, t) for t in sim.trades)
            bt.summary_json, bt.breakdowns_json = json.dumps(summary), json.dumps(results)
            bt.caveats_json = json.dumps(caveats)
            bt.status, bt.finished_at = "done", utc_now_iso()
            db.commit()
            log.info("Backtest %s done: %d scans, %d picks, %d trades", bt_id, len(scans), len(all_picks), len(sim.trades))
        except Exception as exc:
            log.exception("Backtest %s failed", bt_id)
            db.rollback()
            bt = db.get(Backtest, bt_id)
            bt.status, bt.error, bt.finished_at = "failed", redact(f"{type(exc).__name__}: {exc}")[:500], utc_now_iso()
            db.commit()
        finally:
            with _lock:
                _progress.pop(bt_id, None)


def _trade_row(bt_id: int, t: simulate.Trade) -> BacktestTrade:
    return BacktestTrade(
        backtest_id=bt_id, symbol=t.symbol, scan_date=t.scan_date, entry_date=t.entry_date, entry_price=t.entry_price,
        qty=t.qty, invested=t.invested, stop_loss=t.stop_loss, target=t.target, planned_exit_date=t.planned_exit_date,
        signal=t.signal, stage=t.stage, score=t.score, market_cap_bucket=t.market_cap_bucket, sector=t.sector,
        exit_date=t.exit_date, exit_price=t.exit_price, exit_reason=t.exit_reason, pnl=t.pnl, pnl_pct=t.pnl_pct,
        r_multiple=t.r_multiple, days_held=t.days_held, mfe_pct=t.mfe_pct, mae_pct=t.mae_pct, nifty_pct=t.nifty_pct,
        tags_json=json.dumps(t.tags))


def recover_interrupted(db: Session) -> int:
    """Backtests left queued/running by a previous process can never finish; mark them failed."""
    stale = list(db.scalars(select(Backtest).where(Backtest.status.in_(ACTIVE))))
    for bt in stale:
        if bt.id not in _progress:
            bt.status, bt.error, bt.finished_at = "failed", "Interrupted: the server restarted during this backtest.", utc_now_iso()
    db.commit()
    return len(stale)


# --- queries -------------------------------------------------------------------------------------------------------

def get(db: Session, bt_id: int) -> Backtest:
    bt = db.get(Backtest, bt_id)
    if bt is None:
        raise NotFound(f"Backtest {bt_id} not found.")
    return bt


def list_backtests(db: Session, profile_id: int | None = None, limit: int = 20) -> list[Backtest]:
    q = select(Backtest).order_by(Backtest.id.desc()).limit(max(1, min(limit, 100)))
    if profile_id is not None:
        q = q.where(Backtest.profile_id == profile_id)
    return list(db.scalars(q))


def delete(db: Session, bt_id: int) -> None:
    bt = get(db, bt_id)
    if bt.status in ACTIVE:
        raise Conflict("A running backtest cannot be deleted.", backtest_id=bt.id)
    db.delete(bt)
    db.commit()


def to_schema(bt: Backtest) -> dict:
    return {
        "id": bt.id, "profile_id": bt.profile_id, "profile_name": bt.profile.name if bt.profile else "",
        "status": bt.status, "start_date": bt.start_date, "end_date": bt.end_date, "frequency": bt.frequency,
        "entry_rule": bt.entry_rule, "fundamentals_mode": bt.fundamentals_mode, "cost_pct": bt.cost_pct,
        "capital_per_trade": bt.capital_per_trade, "params": json.loads(bt.params_json or "{}"),
        "progress": progress_of(bt), "scan_count": bt.scan_count,
        "summary": json.loads(bt.summary_json) if bt.summary_json else None,
        "caveats": json.loads(bt.caveats_json or "[]"), "error": bt.error, "started_at": bt.started_at,
        "finished_at": bt.finished_at, "created_at": bt.created_at,
    }


TRADE_FIELDS = ("id", "symbol", "scan_date", "entry_date", "entry_price", "qty", "invested", "stop_loss", "target",
                "planned_exit_date", "signal", "stage", "score", "market_cap_bucket", "sector", "exit_date",
                "exit_price", "exit_reason", "pnl", "pnl_pct", "r_multiple", "days_held", "mfe_pct", "mae_pct",
                "nifty_pct")


def results(db: Session, bt_id: int) -> dict:
    bt = get(db, bt_id)
    if bt.status != "done":
        raise Conflict(f"Backtest {bt_id} is {bt.status}; results are available once it is done.", backtest_id=bt.id)
    parts = json.loads(bt.breakdowns_json or "{}")
    trades = [{**{f: getattr(t, f) for f in TRADE_FIELDS}, "tags": json.loads(t.tags_json)} for t in bt.trades]
    return {"backtest": to_schema(bt), **{k: parts.get(k, []) for k in (
        "by_signal", "by_stage", "by_market_cap", "by_sector", "by_month", "loss_patterns", "equity_curve")},
        "trades": trades}
