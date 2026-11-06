"""Fundamentals for a past scan date. No free point-in-time source exists, so a bundle fetched today is made as
honest as possible for the scan date (point_in_time), or fundamentals are left out entirely (technical_only).
"""
from datetime import timedelta

import pandas as pd

PUBLICATION_LAG_DAYS = 45  # results are published roughly 45 days after the period ends
FUNDAMENTAL_PILLARS = ("earnings_acceleration", "fundamental_quality", "valuation")
# Today's values that point_in_time keeps (they would need history we do not have).
KEPT_TODAY = ("returnOnEquity", "debtToEquity", "profitMargins", "operatingMargins", "revenueGrowth")
# Today's values that point_in_time removes because they describe periods after the scan date.
DROPPED_LOOKAHEAD = ("earningsQuarterlyGrowth",)

CAVEATS = {
    "point_in_time": [
        "Fundamentals are one snapshot per stock fetched today. Quarterly and cash-flow rows are dropped if their "
        f"period ended within {PUBLICATION_LAG_DAYS} days before (or after) the scan date, as if not yet published.",
        "P/E is recomputed at each scan date as close ÷ the last four published quarters' EPS (unavailable with fewer "
        "than four); market cap is scaled by the scan-date close; 52-week high/low come from the cut history.",
        "ROE, debt/equity, profit margin, operating margin and revenue growth are today's values, not the values at "
        "each scan date.",
        "Today's latest-quarter earnings growth is removed (it describes a later period), so the earnings pillar is "
        "often unavailable for older scan dates when fewer than five published quarters remain.",
        "Stocks with no fundamentals today (e.g. delisted since) cannot be scored, so they never appear: survivorship bias.",
    ],
    "technical_only": [
        "Technical-only: earnings acceleration, fundamental quality and valuation weights are set to 0 and the rest "
        "renormalised to 100.",
        "P/E, ROE, debt, profit-growth, operating-cash-flow and market-cap rules are skipped (no fundamentals used).",
    ],
    "common": [
        "Fills are at closing prices (next close, or the optimal-entry limit); costs are a flat round-trip "
        "percentage; no slippage or partial fills.",
        "Exit dates count Monday-Friday only; NSE holidays are not modelled.",
    ],
}


def _period_ok(period, cutoff: pd.Timestamp) -> bool:
    try:
        return pd.Timestamp(period) <= cutoff
    except (TypeError, ValueError):
        return False  # an undated row cannot be shown to be published in time


def point_in_time_bundle(bundle: dict, scan_date, scan_close: float, today_close: float | None,
                         history_upto_scan: pd.DataFrame | None = None) -> dict:
    """Return a copy of today's bundle adjusted to what was knowable on `scan_date`."""
    cutoff = pd.Timestamp(scan_date) - timedelta(days=PUBLICATION_LAG_DAYS)
    quarterly = [r for r in (bundle.get("quarterly") or []) if _period_ok(r.get("period"), cutoff)]
    cashflow = [r for r in (bundle.get("cashflow") or []) if _period_ok(r.get("period"), cutoff)]
    info = dict(bundle.get("info") or {})
    for key in DROPPED_LOOKAHEAD:
        info.pop(key, None)

    last4 = [r.get("eps") for r in quarterly[-4:]]
    eps_sum = sum(last4) if len(last4) == 4 and all(e is not None for e in last4) else None
    info["trailingPE"] = (scan_close / eps_sum) if eps_sum not in (None, 0) and scan_close else None

    cap = info.get("marketCap")
    info["marketCap"] = cap * scan_close / today_close if cap and today_close and scan_close else None
    info["currentPrice"] = scan_close
    if history_upto_scan is not None and not history_upto_scan.empty:
        window = history_upto_scan.tail(252)
        info["fiftyTwoWeekHigh"] = float(window["High"].max())
        info["fiftyTwoWeekLow"] = float(window["Low"].min())
    return {"info": info, "quarterly": quarterly, "cashflow": cashflow, "ok": bundle.get("ok", True)}


def technical_only_bundle() -> dict:
    """No fundamentals at all: every fundamentals rule is skipped as 'unavailable'."""
    return {"info": {}, "quarterly": [], "cashflow": [], "ok": True}


def technical_only_weights(weights: dict) -> dict:
    """Fundamental pillars to 0, the others renormalised to sum to 100."""
    rest = {k: float(v) for k, v in weights.items() if k not in FUNDAMENTAL_PILLARS}
    total = sum(rest.values())
    out = {k: 0.0 for k in FUNDAMENTAL_PILLARS}
    if total > 0:
        out.update({k: v * 100 / total for k, v in rest.items()})
    else:  # all remaining weights were 0: share equally
        out.update({k: 100 / len(rest) for k in rest})
    return out
