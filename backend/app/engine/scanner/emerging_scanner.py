"""Emerging Opportunities scanner — the two-stage funnel.

Stage 1 (free, whole NSE market, no per-symbol API calls): every listed
equity gets its price/volume history built from the cached bhavcopy panel,
and a cheap "technical readiness" heuristic ranks the entire universe.

Stage 2 (yfinance, shortlist only): only the top-ranked survivors get
fundamentals + quarterly financials + cash flow fetched and the full
scoring.engine.evaluate() pass run. This keeps a market-wide scan fast and
avoids hammering yfinance across ~2,600 stocks every run.
"""
import os
import pickle
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date

from app.engine import config
from app.engine.data.fetcher import fetch_cashflow_trend, fetch_fundamentals, fetch_quarterly_financials
from app.engine.data.nse_universe import build_market_panel, find_latest_trading_day, symbol_price_history, universe_symbols
from app.engine.scoring.common import scale
from app.engine.scoring.engine import CandidateScore, evaluate
from app.engine.scoring.market_metrics import compute as compute_market_metrics
from app.engine.utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class ScanResult:
    candidates: list[CandidateScore] = field(default_factory=list)
    universe_size: int = 0
    prefiltered_size: int = 0
    scored_size: int = 0
    scan_date: str = ""
    latest_trading_day: str | None = None


def _readiness_heuristic(m) -> float | None:
    """Cheap, technical-indicator-free ranking used only to shrink ~2,600
    stocks down to a shortlist worth spending yfinance calls on. Favors
    stocks that are NOT already extended, showing volume pickup, and
    consolidating — the raw ingredients of an early setup."""
    if not m.available:
        return None

    not_extended = scale(max(m.change_3m_pct or 0, 0), 15, 150, reverse=True)
    volume_pickup = scale(m.volume_ratio_20d or 1.0, 1.0, 3.0)
    consolidation = scale(m.consolidation_range_20d_pct, 8, 45, reverse=True) if m.consolidation_range_20d_pct is not None else 0.5
    off_extreme_low = scale(m.dist_from_52w_high_pct or -100, -80, -5)  # not a dead/broken-down stock either

    return 0.35 * not_extended + 0.3 * volume_pickup + 0.2 * consolidation + 0.15 * off_extreme_low


def _stage1_prefilter(panel) -> list[tuple[str, float]]:
    symbols = universe_symbols(panel)
    ranked = []
    for sym in symbols:
        hist = symbol_price_history(panel, sym)
        if hist.empty or len(hist) < 60:
            continue
        price = float(hist["Close"].iloc[-1])
        if price < config.EMERGING_MIN_PRICE:
            continue
        m = compute_market_metrics(hist)
        readiness = _readiness_heuristic(m)
        if readiness is None:
            continue
        ranked.append((sym, readiness))

    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked


def _fetch_and_score(sym: str, panel) -> CandidateScore | None:
    try:
        hist = symbol_price_history(panel, sym)
        info = fetch_fundamentals(sym)
        quarterly = fetch_quarterly_financials(sym)
        cashflow = fetch_cashflow_trend(sym)
        result = evaluate(sym, hist, info, quarterly, cashflow)

        # ETFs, index funds and G-Sec funds trade in NSE's EQ series alongside
        # real operating companies, and yfinance doesn't reliably flag them —
        # but they carry no fundamentals at all (no sector, no quarterly
        # financials). Fundamentals must matter for this feature (that's the
        # whole point), so a stock with neither fundamental pillar available
        # isn't a candidate, no matter how good its chart looks.
        earn = result.pillars["earnings_acceleration"]
        fq = result.pillars["fundamental_quality"]
        if not earn.available and not fq.available:
            return None

        return result
    except Exception as e:
        log.warning(f"Emerging scan: failed to score {sym}: {e}")
        return None


def _cache_path(trading_day: str, shortlist_size: int) -> str:
    return os.path.join(config.EMERGING_SCAN_CACHE_DIR, f"{trading_day}_{shortlist_size}.pkl")


def _load_cached_scan(trading_day: str, shortlist_size: int) -> ScanResult | None:
    path = _cache_path(trading_day, shortlist_size)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as f:
            result = pickle.load(f)
        if isinstance(result, ScanResult):
            return result
    except Exception as e:
        log.warning(f"Emerging scan: failed to read cache {path}: {e}")
    return None


def _save_cached_scan(trading_day: str, shortlist_size: int, result: ScanResult) -> None:
    os.makedirs(config.EMERGING_SCAN_CACHE_DIR, exist_ok=True)
    path = _cache_path(trading_day, shortlist_size)
    try:
        with open(path, "wb") as f:
            pickle.dump(result, f)
    except Exception as e:
        log.warning(f"Emerging scan: failed to write cache {path}: {e}")


def run_scan(shortlist_size: int = config.EMERGING_SHORTLIST_SIZE, max_workers: int = 6,
             progress_callback=None, use_cache: bool = True) -> ScanResult:
    # Cheap check first: know "what trading day is it" without building the
    # full ~270-day panel, so a same-day cache hit doesn't pay that cost.
    latest_day = find_latest_trading_day()
    trading_day = str(latest_day) if latest_day is not None else None

    if use_cache and trading_day is not None:
        cached = _load_cached_scan(trading_day, shortlist_size)
        if cached is not None:
            log.info(f"Emerging scan: serving cached result for {trading_day} (shortlist={shortlist_size})")
            return cached

    panel = build_market_panel()
    universe = universe_symbols(panel)

    ranked = _stage1_prefilter(panel)
    shortlist = [sym for sym, _ in ranked[:shortlist_size]]

    candidates: list[CandidateScore] = []
    with ThreadPoolExecutor(max_workers=max_workers) as exe:
        futures = {exe.submit(_fetch_and_score, sym, panel): sym for sym in shortlist}
        done = 0
        for future in as_completed(futures):
            done += 1
            if progress_callback:
                progress_callback(done, len(shortlist), futures[future])
            result = future.result()
            if result is not None and result.total_score is not None:
                candidates.append(result)

    candidates.sort(key=lambda c: c.total_score, reverse=True)

    result = ScanResult(
        candidates=candidates,
        universe_size=len(universe),
        prefiltered_size=len(shortlist),
        scored_size=len(candidates),
        scan_date=date.today().isoformat(),
        latest_trading_day=trading_day,
    )

    if trading_day is not None:
        _save_cached_scan(trading_day, shortlist_size, result)

    return result
