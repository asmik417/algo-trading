"""One scan date: cut every history at the scan date, then run the same pipeline as a full run
(prefilter -> shortlist -> score -> hard filters -> plan). The pipeline steps are passed in by the caller
(services pass suggestion_service / plan_service), so this module stays pure and nothing is duplicated.
"""
from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd

from app.engine.backtest.history import avg_turnover_lacs, upto, upto_all
from app.engine.scoring.buckets import market_cap_bucket


@dataclass(frozen=True)
class Pick:
    symbol: str
    scan_date: pd.Timestamp
    rank: int
    score: float
    signal: str
    stage: str
    market_cap_bucket: str
    sector: str | None
    entry_optimal: float
    stop_loss: float
    target: float
    planned_exit_date: str
    avg_turnover_lacs: float | None


def shortlist(scan_date, histories: dict[str, pd.DataFrame], params, prefilter: Callable) -> list[str]:
    """Stage 1 on histories cut at the scan date."""
    day = pd.Timestamp(scan_date)
    return prefilter(day.date().isoformat(), upto_all(histories, day), params)


def picks(scan_date, histories: dict[str, pd.DataFrame], symbols: list[str], params, *, score: Callable,
          plan: Callable, bundle_for: Callable, max_suggestions: int) -> list[Pick]:
    """Stage 2 for `symbols` on histories cut at the scan date.
    score(sym, history, bundle, params) -> object with .candidate and .failures (suggestion_service.score_symbol)
    plan(history, stage, params, trading_day) -> object with plan fields, or None (plan_service.build_plan)
    bundle_for(sym, scan_date, history) -> fundamentals bundle as of the scan date."""
    day = pd.Timestamp(scan_date)
    iso = day.date().isoformat()
    passed = []
    for sym in symbols:
        h = histories.get(sym)
        if h is None:
            continue
        h = upto(h, day)  # the single no-look-ahead boundary (history.upto), shared with shortlist()
        if h.empty or h.index[-1] != day:
            continue
        bundle = bundle_for(sym, day, h)
        s = score(sym, h, bundle, params)
        if s.candidate.total_score is None or s.failures:
            continue
        passed.append((s, h, bundle))
    passed.sort(key=lambda t: t[0].candidate.total_score, reverse=True)

    out: list[Pick] = []
    for s, h, bundle in passed:
        if len(out) >= max_suggestions:
            break
        p = plan(h, s.candidate.stage, params, iso)
        if p is None:
            continue
        c = s.candidate
        out.append(Pick(symbol=c.symbol, scan_date=day, rank=len(out) + 1, score=round(float(c.total_score), 2),
                        signal=c.signal, stage=c.stage, market_cap_bucket=market_cap_bucket(c.market_cap),
                        sector=(bundle.get("info") or {}).get("sector") or None, entry_optimal=p.entry_optimal,
                        stop_loss=p.stop_loss, target=p.target, planned_exit_date=p.planned_exit_date,
                        avg_turnover_lacs=avg_turnover_lacs(h)))
    return out
