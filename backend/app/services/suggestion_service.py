"""Runs the algo for a profile (prefilter -> fundamentals -> score -> hard filters -> plan -> save) in a thread.
Also ad-hoc single-stock analysis from Explore (saved as source="explore"), and the run/suggestion queries.
"""
import json
import os
import pickle
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session, object_session

from app.core.clock import utc_now_iso
from app.core.redaction import redact
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.engine import config as engine_config
from app.engine.data import fetcher
from app.engine.params import ScreenParams
from app.engine.scanner.emerging_scanner import _readiness_heuristic
from app.engine.scoring.buckets import market_cap_bucket
from app.engine.scoring.engine import CandidateScore, evaluate
from app.engine.scoring.market_metrics import compute as compute_market_metrics
from app.engine.scoring.signal import SIGNALS
from app.models import Suggestion, SuggestionRun
from app.services import analysis_service, market_data, plan_service, profile_service, run_registry
from app.services.analysis_service import num
from app.services.errors import BadInput, NotFound

log = get_logger(__name__)

MIN_HISTORY_ROWS = 60
FETCH_WORKERS = 6
NO_FUNDAMENTALS = "No fundamentals available (ETF, fund or data missing)"


# --- fundamentals cache --------------------------------------------------------------

def _fundamentals_path(trading_day: str, symbol: str) -> str:
    return os.path.join(engine_config.FUNDAMENTALS_CACHE_DIR, trading_day, f"{symbol}.pkl")


def load_fundamentals(trading_day: str, symbol: str, force_refetch: bool = False) -> dict:
    """{info, quarterly, cashflow} for (trading_day, symbol): disk cache first, else yfinance.
    Only successful fetches are cached, so a failure is retried next run."""
    path = _fundamentals_path(trading_day, symbol)
    if not force_refetch and os.path.exists(path):
        try:
            with open(path, "rb") as f:
                return pickle.load(f)
        except Exception:
            log.warning("Unreadable fundamentals cache %s; refetching", path)
    bundle = fetcher.fetch_fundamental_bundle(symbol)
    if bundle.get("ok"):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = f"{path}.{threading.get_ident()}.tmp"
        with open(tmp, "wb") as f:
            pickle.dump(bundle, f)
        os.replace(tmp, path)
    return bundle


# --- stage 1: cheap whole-market prefilter ----------------------------------------------

_stage1_cache: dict[str, list[tuple[str, float, float, float]]] = {}
_stage1_lock = threading.Lock()


def _stage1_rows(trading_day: str, histories: dict[str, pd.DataFrame]) -> list[tuple[str, float, float, float]]:
    """(symbol, readiness, last close, 20-day avg turnover) for every stock that traded on trading_day.
    Independent of profile params, so it is computed once per trading day."""
    with _stage1_lock:
        if trading_day in _stage1_cache:
            return _stage1_cache[trading_day]
        last = pd.Timestamp(trading_day)
        rows = []
        for sym, hist in histories.items():
            if len(hist) < MIN_HISTORY_ROWS or hist.index[-1] != last:
                continue
            readiness = _readiness_heuristic(compute_market_metrics(hist))
            if readiness is None:
                continue
            turnover = float(hist["TurnoverLacs"].tail(20).mean()) if "TurnoverLacs" in hist else float("nan")
            rows.append((sym, readiness, float(hist["Close"].iloc[-1]), turnover))
        rows.sort(key=lambda r: r[1], reverse=True)
        _stage1_cache.clear()
        _stage1_cache[trading_day] = rows
        return rows


def universe_size(trading_day: str, histories: dict[str, pd.DataFrame]) -> int:
    last = pd.Timestamp(trading_day)
    return sum(1 for h in histories.values() if len(h) and h.index[-1] == last)


def prefilter(trading_day: str, histories: dict[str, pd.DataFrame], params: ScreenParams) -> list[str]:
    min_price, min_turnover = float(params.min_price), float(params.min_avg_turnover_lacs)
    keep = [sym for sym, _, price, turnover in _stage1_rows(trading_day, histories)
            if price >= min_price and (turnover != turnover or turnover >= min_turnover)]  # NaN turnover: unknown, keep
    return keep[: int(params.shortlist_size)]


# --- stage 2: score + hard filters ---------------------------------------------------------

@dataclass
class Scored:
    candidate: CandidateScore
    bundle: dict
    indicators: dict
    failures: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)   # filters not applied because the metric is missing
    rules_checked: int = 0                              # filters actually evaluated (pass or fail); verdict.rules.total
    market: dict = field(default_factory=dict)          # whole-market facts for the day (market_data.market_context)

    @property
    def has_fundamentals(self) -> bool:
        p = self.candidate.pillars
        return p["earnings_acceleration"].available or p["fundamental_quality"].available


def _latest_ocf(cashflow: list[dict]) -> float | None:
    for row in reversed(cashflow or []):
        if row.get("ocf") is not None:
            return float(row["ocf"])
    return None


def filter_failures(s: Scored, params: ScreenParams) -> tuple[list[str], list[str], int]:
    """(failures, skipped, checked) for the profile's hard filters. A missing metric skips its filter
    ("ROE unavailable, filter skipped") and is not counted in `checked`; a filter switched off is neither."""
    c, info, ind, m = s.candidate, s.bundle.get("info") or {}, s.indicators, s.candidate.market
    out: list[str] = []
    skipped: list[str] = []
    checked = 0

    def skip(what: str) -> None:
        skipped.append(f"{what} unavailable, filter skipped")

    def rule(failure: str | None) -> None:
        """Record one evaluated filter; `failure` is the message when it fails, None when it passes."""
        nonlocal checked
        checked += 1
        if failure:
            out.append(failure)

    if c.market_cap is None:
        skip("Market cap")
    else:
        bucket = market_cap_bucket(c.market_cap)
        rule(None if bucket in params.allowed_caps
             else f"Market cap bucket {bucket} not in allowed ({', '.join(params.allowed_caps)})")
    if params.max_pe > 0:
        pe = num(info.get("trailingPE"))
        if pe is None:
            skip("P/E")
        elif pe <= 0:
            rule(f"P/E {pe:.0f} is negative (loss-making)")
        else:
            rule(f"P/E {pe:.0f} above max {params.max_pe:.0f}" if pe > params.max_pe else None)
    roe = num(info.get("returnOnEquity"), 6)
    if roe is None:
        skip("ROE")
    else:
        rule(f"ROE {roe * 100:.1f}% below min {params.min_roe_pct:.0f}%" if roe * 100 < params.min_roe_pct else None)
    if params.max_debt_to_equity > 0:
        de = num(info.get("debtToEquity"))
        if de is None:
            skip("Debt/equity")
        else:
            rule(f"Debt/equity {de:.0f}% above max {params.max_debt_to_equity:.0f}%"
                 if de > params.max_debt_to_equity else None)
    growth = num(c.profit_yoy_pct)
    if growth is None:
        skip("Profit growth")
    else:
        rule(f"Profit growth {growth:.0f}% below min {params.min_profit_growth_pct:.0f}%"
             if growth < params.min_profit_growth_pct else None)
    if params.require_positive_ocf:
        ocf = _latest_ocf(s.bundle.get("cashflow"))
        if ocf is None:
            skip("Operating cash flow")
        else:
            rule("Operating cash flow is negative" if ocf <= 0 else None)
    rsi = ind.get("rsi")
    if rsi is None:
        skip("RSI")
    elif rsi < params.rsi_min:
        rule(f"RSI {rsi:.0f} below min {params.rsi_min:.0f}")
    else:
        rule(f"RSI {rsi:.0f} above max {params.rsi_max:.0f}" if rsi > params.rsi_max else None)
    if params.require_above_200ema:
        trend = ind.get("ema_trend")
        if ind.get("ema200") is None or trend is None:
            skip("200-day EMA")
        else:
            rule(None if trend.startswith(("STRONG_UPTREND", "ABOVE_200EMA")) else "Price is below the 200-day EMA")
    runup = m.change_3m_pct if m is not None else None
    if runup is None:
        skip("3-month run-up")
    else:
        rule(f"3-month run-up {runup:.0f}% above max {params.max_3m_runup_pct:.0f}%"
             if runup > params.max_3m_runup_pct else None)
    if params.max_dist_from_52w_high_pct > 0:
        dist = m.dist_from_52w_high_pct if m is not None else None  # 0 = at the high, negative = below it
        if dist is None:
            skip("Distance from 52-week high")
        else:
            rule(f"{-dist:.0f}% below 52-week high, more than max {params.max_dist_from_52w_high_pct:.0f}%"
                 if -dist > params.max_dist_from_52w_high_pct else None)
    vol = m.volume_ratio_20d if m is not None else None
    if vol is None:
        skip("Volume ratio")
    else:
        rule(f"Volume {vol:.2f}x 20-day average, below min {params.min_volume_ratio:.2f}x"
             if vol < params.min_volume_ratio else None)
    if params.min_nifty_vs_ema50_pct > 0:
        nifty = s.market.get("nifty_vs_ema50_pct")
        if nifty is None:
            skip("Nifty 50 trend")
        else:
            rule(f"Nifty 50 is {-nifty:.1f}% below its 50-day EMA, more than max {params.min_nifty_vs_ema50_pct:g}%: "
                 "no new picks today" if nifty < -params.min_nifty_vs_ema50_pct else None)
    if c.total_score is not None:
        rule(f"Score {c.total_score:.0f} below min {params.min_score:.0f}" if c.total_score < params.min_score else None)
    rule(f"Signal is {SIGNALS['WEAK']}" if c.signal == SIGNALS["WEAK"] else None)
    return out, skipped, checked


CORPORATE_ACTION_MOVE = 0.40
CORPORATE_ACTION_WINDOW = 130  # trading days


def corporate_action_date(history: pd.DataFrame) -> str | None:
    """Most recent day in the last 130 sessions with a one-day close move over 40% (likely an unadjusted
    split/bonus/consolidation in the bhavcopy prices), else None."""
    if history is None or len(history) < 2:
        return None
    moves = history["Close"].tail(CORPORATE_ACTION_WINDOW + 1).pct_change().tail(CORPORATE_ACTION_WINDOW)
    hits = moves[moves.abs() > CORPORATE_ACTION_MOVE]
    return hits.index[-1].date().isoformat() if not hits.empty else None


def score_symbol(symbol: str, history: pd.DataFrame, bundle: dict, params: ScreenParams,
                 require_fundamentals: bool = True, market: dict | None = None) -> Scored:
    """Score + hard filters for one stock. `require_fundamentals=False` (backtest technical_only mode) drops the
    has-fundamentals rule; everything else is the same pipeline as a full run."""
    candidate = evaluate(symbol, history, bundle.get("info") or {}, bundle.get("quarterly") or [],
                         bundle.get("cashflow") or [], weights=params.weights)
    s = Scored(candidate=candidate, bundle=bundle, indicators=analysis_service.indicators(history), market=market or {})
    s.failures, s.skipped, s.rules_checked = filter_failures(s, params)
    # Two more rules, always evaluated and listed first when they fail.
    gap_day = corporate_action_date(history)
    s.rules_checked += 2 if require_fundamentals else 1
    if gap_day is not None:
        s.failures.insert(0, f"Possible corporate action on {gap_day}, excluded")
    if require_fundamentals and not s.has_fundamentals:  # full runs drop these; Explore/watchlist show why
        s.failures.insert(0, NO_FUNDAMENTALS)
    return s


def _payload(s: Scored, params: ScreenParams) -> dict:
    c, m = s.candidate, s.candidate.market
    info = s.bundle.get("info") or {}
    return {
        "total_score": num(c.total_score, 4), "data_coverage": num(c.data_coverage, 4),
        "pillars": analysis_service.pillars_payload(c),
        "score_breakdown": analysis_service.score_breakdown(c, params.weights),
        "indicators": s.indicators,
        "fundamentals": analysis_service.fundamentals(info, c),
        "market_cap_bucket": market_cap_bucket(c.market_cap),
        "sector": info.get("sector") or None,
        "profit_yoy_pct": num(c.profit_yoy_pct),
        "change_1m_pct": num(m.change_1m_pct) if m else None,
        "change_3m_pct": num(m.change_3m_pct) if m else None,
        "volume_ratio_20d": num(m.volume_ratio_20d) if m else None,
        # Contract: when the stock passes, `failures` lists filters skipped for missing data instead.
        "filters": {"passed": not s.failures, "failures": list(s.failures) if s.failures else list(s.skipped)},
        "verdict": verdict_of(s),
    }


def verdict_of(s: Scored) -> dict:
    ind, m = s.indicators, s.candidate.market
    volume = ind.get("volume_ratio") if ind.get("volume_ratio") is not None else (m.volume_ratio_20d if m else None)
    return analysis_service.build_verdict(s.failures, s.rules_checked, s.candidate.signal, s.candidate.stage,
                                          ind.get("ema_trend"), ind.get("rsi"), volume, num(s.candidate.profit_yoy_pct))


def _params_for(db: Session, row: Suggestion) -> ScreenParams:
    """The parameters a stored suggestion was scored under: its run's snapshot, else (Explore) the profile's."""
    if row.run_id is not None and (run := db.get(SuggestionRun, row.run_id)) is not None:
        return ScreenParams.from_json(run.params_json)
    return profile_service.params_of(profile_service.get_profile(db, row.profile_id))


def backfill_verdict(row: Suggestion) -> dict:
    """Verdict for a row saved before verdicts existed: re-score it exactly as it was scored (history up to its
    trading day, that day's cached fundamentals, its run's params), then save it into payload_json once."""
    db = object_session(row)
    payload = json.loads(row.payload_json or "{}")
    try:
        hist = market_data.history(row.symbol)
        hist = hist.loc[hist.index <= pd.Timestamp(row.trading_day)]
        if hist.empty:
            raise ValueError("no price history up to the suggestion day")
        s = score_symbol(row.symbol, hist, load_fundamentals(row.trading_day, row.symbol), _params_for(db, row))
        verdict = verdict_of(s)
    except Exception:
        log.warning("Verdict backfill for suggestion %s (%s) fell back to stored filters", row.id, row.symbol,
                    exc_info=True)
        stored = payload.get("filters") or {}
        failures = [] if stored.get("passed", True) else list(stored.get("failures", []))
        ind = payload.get("indicators") or {}
        # Without a re-score the evaluated-filter count is unknown; only the stored failures are certain.
        verdict = analysis_service.build_verdict(failures, len(failures), row.signal, row.stage, ind.get("ema_trend"),
                                                 ind.get("rsi"), ind.get("volume_ratio"), payload.get("profit_yoy_pct"))
    payload["verdict"] = verdict
    row.payload_json = json.dumps(payload)
    if db is not None:
        db.commit()
    return verdict


def _suggestion_row(s: Scored, plan: plan_service.Plan, params: ScreenParams, profile_id: int, trading_day: str,
                    *, run_id: int | None, rank: int | None, source: str, price: float) -> Suggestion:
    c = s.candidate
    return Suggestion(
        run_id=run_id, source=source, profile_id=profile_id, symbol=c.symbol, trading_day=trading_day, rank=rank,
        score=round(float(c.total_score), 2), stage=c.stage, signal=c.signal, price=round(price, 2),
        entry_aggressive=plan.entry_aggressive, entry_optimal=plan.entry_optimal,
        entry_conservative=plan.entry_conservative, stop_loss=plan.stop_loss, target=plan.target,
        risk_reward=plan.risk_reward, horizon_days=plan.horizon_days, planned_exit_date=plan.planned_exit_date,
        timing_note=plan.timing_note, exit_note=plan.exit_note,
        positives_json=json.dumps(list(c.positives)), risks_json=json.dumps(list(c.risks)),
        payload_json=json.dumps(_payload(s, params)),
    )


# --- runs ------------------------------------------------------------------------------

def _spawn(run_id: int, force_refetch: bool) -> None:
    threading.Thread(target=execute_run, args=(run_id, force_refetch), name=f"run-{run_id}", daemon=True).start()


def start_run(db: Session, profile_id: int, force_refetch: bool = False) -> tuple[SuggestionRun, bool]:
    """Queue a run in the background. Returns (run, created); created=False means one was already active."""
    profile = profile_service.get_profile(db, profile_id)
    active = run_registry.active_run(profile_id)
    if active is not None and (existing := db.get(SuggestionRun, active)) is not None:
        return existing, False
    run = SuggestionRun(profile_id=profile_id, status="queued", params_json=profile.params_json)
    db.add(run)
    db.commit()
    raced = run_registry.start(run.id, profile_id)
    if raced is not None:
        db.delete(run)
        db.commit()
        return db.get(SuggestionRun, raced), False
    _spawn(run.id, force_refetch)
    return run, True


def execute_run(run_id: int, force_refetch: bool = False) -> None:
    with SessionLocal() as db:
        run = db.get(SuggestionRun, run_id)
        params = ScreenParams.from_json(run.params_json)
        try:
            run.status, run.started_at = "running", utc_now_iso()
            db.commit()
            run_registry.update(run_id, status="running", phase="panel")

            trading_day = market_data.panel_day()
            if not trading_day:
                raise RuntimeError("No market data available (bhavcopy panel is empty)")
            histories = market_data.all_histories()
            run.trading_day = trading_day
            run.universe_size = universe_size(trading_day, histories)
            db.commit()

            run_registry.update(run_id, phase="prefilter")
            shortlist = prefilter(trading_day, histories, params)

            run_registry.update(run_id, phase="scoring", done=0, total=len(shortlist))
            market = market_data.market_context(trading_day) if params.min_nifty_vs_ema50_pct > 0 else {}
            scored = _score_shortlist(run_id, shortlist, histories, trading_day, params, force_refetch, market)
            run.scored_size = len(scored)
            db.commit()

            run_registry.update(run_id, phase="filtering", current_symbol=None)
            passed = sorted((s for s in scored if not s.failures), key=lambda s: s.candidate.total_score, reverse=True)
            run.passed_size = len(passed)

            run_registry.update(run_id, phase="planning")
            rows, rank = [], 0
            for s in passed[: int(params.max_suggestions)]:
                hist = histories[s.candidate.symbol]
                plan = plan_service.build_plan(hist, s.candidate.stage, params, trading_day)
                if plan is None:
                    log.warning("Run %s: no plan for %s (history too short); skipped", run_id, s.candidate.symbol)
                    continue
                rank += 1
                rows.append(_suggestion_row(s, plan, params, run.profile_id, trading_day, run_id=run_id, rank=rank,
                                            source="run", price=float(hist["Close"].iloc[-1])))

            run_registry.update(run_id, phase="saving")
            db.add_all(rows)
            run.status, run.finished_at = "done", utc_now_iso()
            db.commit()
            run_registry.finish(run_id, "done")
            log.info("Run %s done: universe %s, shortlist %s, scored %s, passed %s, saved %s",
                     run_id, run.universe_size, len(shortlist), run.scored_size, run.passed_size, len(rows))
        except Exception as exc:
            log.exception("Run %s failed", run_id)
            db.rollback()
            run = db.get(SuggestionRun, run_id)
            run.status, run.error, run.finished_at = "failed", redact(f"{type(exc).__name__}: {exc}")[:500], utc_now_iso()
            db.commit()
            run_registry.finish(run_id, "failed")


def _score_shortlist(run_id, shortlist, histories, trading_day, params, force_refetch, market=None) -> list[Scored]:
    def work(sym: str) -> Scored | None:
        bundle = load_fundamentals(trading_day, sym, force_refetch)
        s = score_symbol(sym, histories[sym], bundle, params, market=market)
        # ETFs / funds trade in the EQ series but have no fundamentals; this algo is about fundamentals.
        if not s.has_fundamentals or s.candidate.total_score is None:
            return None
        return s

    out: list[Scored] = []
    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
        futures = {pool.submit(work, sym): sym for sym in shortlist}
        for i, fut in enumerate(as_completed(futures), start=1):
            sym = futures[fut]
            run_registry.update(run_id, done=i, current_symbol=sym)
            try:
                s = fut.result()
            except Exception:
                log.warning("Run %s: scoring %s failed", run_id, sym, exc_info=True)
                continue
            if s is not None:
                out.append(s)
    return out


def recover_interrupted_runs(db: Session) -> int:
    """Runs left queued/running by a previous process can never finish; mark them failed."""
    stale = list(db.scalars(select(SuggestionRun).where(SuggestionRun.status.in_(("queued", "running")))))
    for run in stale:
        if run_registry.get(run.id) is None:
            run.status, run.error, run.finished_at = "failed", "Interrupted: the server restarted during this run.", utc_now_iso()
    db.commit()
    return len(stale)


# --- single-symbol analysis (Explore and watchlist runs) ------------------------------------

def analyze_one(symbol: str, params: ScreenParams, trading_day: str | None,
                force_refetch: bool = False) -> tuple[Scored, plan_service.Plan, float]:
    """Score + filter + plan one stock under `params`. Raises NotFound (not in the universe today) or
    BadInput (cannot be scored or planned). Fundamentals come from the same per-day cache as full runs."""
    sym = symbol.strip().upper()
    hist = market_data.history(sym)
    if not trading_day or hist.empty or hist.index[-1] != pd.Timestamp(trading_day):
        raise NotFound(f"{sym} is not in the NSE universe for {trading_day}.")
    market = market_data.market_context(trading_day) if params.min_nifty_vs_ema50_pct > 0 else {}
    s = score_symbol(sym, hist, load_fundamentals(trading_day, sym, force_refetch), params, market=market)
    if s.candidate.total_score is None:
        raise BadInput(f"Not enough data to score {sym}.")
    plan = plan_service.build_plan(hist, s.candidate.stage, params, trading_day)
    if plan is None:
        raise BadInput(f"Not enough price history to build a plan for {sym}.")
    return s, plan, float(hist["Close"].iloc[-1])


def analyze_symbol(db: Session, symbol: str, profile_id: int) -> dict:
    """Score one stock under a profile, save it as an explore suggestion, return its SuggestionDetail."""
    profile = profile_service.get_profile(db, profile_id)
    params = profile_service.params_of(profile)
    trading_day = market_data.panel_day()
    s, plan, price = analyze_one(symbol, params, trading_day)
    row = _suggestion_row(s, plan, params, profile.id, trading_day, run_id=None, rank=None, source="explore",
                          price=price)
    db.add(row)
    db.commit()
    return analysis_service.build_detail(db, row)


# --- watchlist runs ------------------------------------------------------------------------------

MAX_WATCHLIST = 50
MAX_SYMBOL_LEN = 30


def clean_watchlist(symbols: list[str]) -> list[str]:
    """Upper-case, strip, drop blanks, de-duplicate keeping first-seen order; 1-50 symbols or 400."""
    out: list[str] = []
    for raw in symbols:
        sym = (raw or "").strip().upper()
        if not sym:
            continue
        if len(sym) > MAX_SYMBOL_LEN:
            raise BadInput(f"'{sym[:MAX_SYMBOL_LEN]}...' is not a valid NSE symbol.")
        if sym not in out:
            out.append(sym)
    if not out:
        raise BadInput("Give at least one symbol.")
    if len(out) > MAX_WATCHLIST:
        raise BadInput(f"A watchlist run takes at most {MAX_WATCHLIST} symbols; got {len(out)}.")
    return out


def _spawn_watchlist(run_id: int) -> None:
    threading.Thread(target=execute_watchlist_run, args=(run_id,), name=f"watchlist-{run_id}", daemon=True).start()


def start_watchlist_run(db: Session, profile_id: int, symbols: list[str] | None = None,
                        list_id: int | None = None) -> SuggestionRun:
    """Exactly one of `symbols` / `list_id`. With a list, its current symbols are copied into the run, so the
    run stays readable after the list is edited or deleted."""
    profile = profile_service.get_profile(db, profile_id)
    if (symbols is None) == (list_id is None):
        raise BadInput("Give either list_id or symbols, not both and not neither.")
    if list_id is not None:
        from app.models import PickList

        pick_list = db.get(PickList, list_id)
        if pick_list is None:
            raise NotFound(f"Pick list {list_id} not found.")
        cleaned = json.loads(pick_list.symbols_json)
    else:
        cleaned = clean_watchlist(symbols)
    run = SuggestionRun(profile_id=profile_id, status="queued", kind="watchlist", symbols_json=json.dumps(cleaned),
                        list_id=list_id, params_json=profile.params_json)
    db.add(run)
    db.commit()
    run_registry.start(run.id, profile_id, exclusive=False)
    _spawn_watchlist(run.id)
    return run


def execute_watchlist_run(run_id: int) -> None:
    """analyze_one() per symbol (in parallel); every analysable symbol is saved as a source="watchlist"
    suggestion, passing the filters or not. Unknown/unscorable symbols are recorded as item errors."""
    with SessionLocal() as db:
        run = db.get(SuggestionRun, run_id)
        params = ScreenParams.from_json(run.params_json)
        symbols: list[str] = json.loads(run.symbols_json or "[]")
        try:
            run.status, run.started_at = "running", utc_now_iso()
            db.commit()
            run_registry.update(run_id, status="running", phase="panel")
            trading_day = market_data.panel_day()
            if not trading_day:
                raise RuntimeError("No market data available (bhavcopy panel is empty)")
            run.trading_day, run.universe_size = trading_day, len(symbols)
            db.commit()

            run_registry.update(run_id, phase="scoring", done=0, total=len(symbols))
            analysed: dict[str, tuple] = {}
            errors: dict[str, str] = {}
            with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
                futures = {pool.submit(analyze_one, sym, params, trading_day): sym for sym in symbols}
                for i, fut in enumerate(as_completed(futures), start=1):
                    sym = futures[fut]
                    run_registry.update(run_id, done=i, current_symbol=sym)
                    try:
                        analysed[sym] = fut.result()
                    except (NotFound, BadInput) as exc:
                        errors[sym] = exc.detail
                    except Exception as exc:
                        log.warning("Watchlist run %s: %s failed", run_id, sym, exc_info=True)
                        errors[sym] = redact(f"Could not analyse {sym}: {type(exc).__name__}")

            run_registry.update(run_id, phase="saving", current_symbol=None)
            db.add_all(_suggestion_row(s, plan, params, run.profile_id, trading_day, run_id=run_id, rank=None,
                                       source="watchlist", price=price)
                       for sym in symbols if sym in analysed for s, plan, price in [analysed[sym]])
            run.scored_size = len(analysed)
            run.passed_size = sum(1 for s, _, _ in analysed.values() if not s.failures)
            run.item_errors_json = json.dumps(errors)
            run.status, run.finished_at = "done", utc_now_iso()
            db.commit()
            run_registry.finish(run_id, "done")
            log.info("Watchlist run %s done: %d symbols, %d analysed, %d passed, %d errors",
                     run_id, len(symbols), run.scored_size, run.passed_size, len(errors))
        except Exception as exc:
            log.exception("Watchlist run %s failed", run_id)
            db.rollback()
            run = db.get(SuggestionRun, run_id)
            run.status, run.error, run.finished_at = "failed", redact(f"{type(exc).__name__}: {exc}")[:500], utc_now_iso()
            db.commit()
            run_registry.finish(run_id, "failed")


def _error_item(symbol: str, error: str) -> dict:
    """WatchlistMiss: a symbol with no suggestion row. Nothing was scored, so nothing can be tracked."""
    return {"id": None, "symbol": symbol, "error": error, "filters": None, "score": None, "signal": None,
            "stage": None, "price": None, "is_tracked": False, "position_id": None}


def watchlist_results(db: Session, run_id: int) -> dict:
    """Items in the order the symbols were requested; a symbol still being analysed is not listed yet."""
    run = get_run(db, run_id)
    if run.kind != "watchlist":
        raise BadInput(f"Run {run_id} is a full run; its picks are at GET /profiles/{run.profile_id}/suggestions?run_id={run_id}.")
    rows = {r.symbol: r for r in db.scalars(select(Suggestion).where(Suggestion.run_id == run.id,
                                                                     Suggestion.source == "watchlist"))}
    errors: dict[str, str] = json.loads(run.item_errors_json or "{}")
    lookup = analysis_service.tracking_lookup(db, run.profile_id)
    items = []
    for sym in json.loads(run.symbols_json or "[]"):
        if sym in rows:
            item = analysis_service.summary(rows[sym], lookup)
            item["filters"] = json.loads(rows[sym].payload_json or "{}").get("filters", {"passed": True, "failures": []})
            item["error"] = None
            items.append(item)
        elif sym in errors:
            items.append(_error_item(sym, errors[sym]))
    return {"run": run_to_schema(run), "items": items}


def list_watchlist_runs(db: Session, profile_id: int, limit: int = 10, list_id: int | None = None) -> list[SuggestionRun]:
    """Newest first; `list_id` narrows to runs of one pick list (a deleted or unknown list simply matches none)."""
    profile_service.get_profile(db, profile_id)
    q = select(SuggestionRun).where(SuggestionRun.profile_id == profile_id, SuggestionRun.kind == "watchlist")
    if list_id is not None:
        q = q.where(SuggestionRun.list_id == list_id)
    q = q.order_by(SuggestionRun.id.desc()).limit(max(1, min(limit, 100)))
    return list(db.scalars(q))


# --- queries ------------------------------------------------------------------------------------

def run_to_schema(run: SuggestionRun) -> dict:
    live = run_registry.get(run.id)
    if live is not None:
        progress = {k: live[k] for k in ("phase", "done", "total", "current_symbol")}
    elif run.status == "done":
        n = run.scored_size or 0
        progress = {"phase": "done", "done": n, "total": n, "current_symbol": None}
    else:
        progress = {"phase": "done" if run.status == "failed" else "panel", "done": 0, "total": 0,
                    "current_symbol": None}
    return {
        "id": run.id, "profile_id": run.profile_id, "status": run.status, "kind": run.kind or "full",
        "symbols": json.loads(run.symbols_json) if run.symbols_json else None,
        "list_id": run.list_id, "list_name": run.pick_list.name if run.list_id and run.pick_list else None,  # name now
        "trading_day": run.trading_day,
        "progress": progress, "universe_size": run.universe_size, "scored_size": run.scored_size,
        "passed_size": run.passed_size, "error": run.error, "started_at": run.started_at,
        "finished_at": run.finished_at, "created_at": run.created_at,
    }


def get_run(db: Session, run_id: int) -> SuggestionRun:
    run = db.get(SuggestionRun, run_id)
    if run is None:
        raise NotFound(f"Run {run_id} not found.")
    return run


def list_runs(db: Session, profile_id: int, limit: int = 10) -> list[SuggestionRun]:
    profile_service.get_profile(db, profile_id)
    q = (select(SuggestionRun).where(SuggestionRun.profile_id == profile_id, SuggestionRun.kind == "full")
         .order_by(SuggestionRun.id.desc()).limit(max(1, min(limit, 100))))
    return list(db.scalars(q))


def suggestions_for(db: Session, profile_id: int, run_ref: str = "latest") -> dict:
    profile_service.get_profile(db, profile_id)
    if run_ref in ("", "latest"):
        run = db.scalar(select(SuggestionRun)
                        .where(SuggestionRun.profile_id == profile_id, SuggestionRun.status == "done",
                               SuggestionRun.kind == "full")
                        .order_by(SuggestionRun.id.desc()).limit(1))
    else:
        if not run_ref.isdigit():
            raise BadInput("run_id must be 'latest' or a run number.")
        run = db.get(SuggestionRun, int(run_ref))
        if run is None or run.profile_id != profile_id:
            raise NotFound(f"Run {run_ref} not found for profile {profile_id}.")
    if run is None:
        return {"run": None, "items": []}
    rows = list(db.scalars(select(Suggestion).where(Suggestion.run_id == run.id, Suggestion.source == "run")
                           .order_by(Suggestion.rank)))
    lookup = analysis_service.tracking_lookup(db, profile_id)
    return {"run": run_to_schema(run), "items": [analysis_service.summary(r, lookup) for r in rows]}


def get_suggestion(db: Session, suggestion_id: int) -> Suggestion:
    row = db.get(Suggestion, suggestion_id)
    if row is None:
        raise NotFound(f"Suggestion {suggestion_id} not found.")
    return row


def suggestion_detail(db: Session, suggestion_id: int) -> dict:
    return analysis_service.build_detail(db, get_suggestion(db, suggestion_id))
