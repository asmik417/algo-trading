"""Small display/filter groupings derived from already-computed fields —
no new data sources, just bucketing for the UI filters."""

_LARGE_CAP_CUTOFF = 20_000 * 1e7   # ~₹20,000 Cr
_MID_CAP_CUTOFF = 5_000 * 1e7      # ~₹5,000 Cr


def market_cap_bucket(market_cap: float | None) -> str:
    if market_cap is None:
        return "Unknown"
    if market_cap >= _LARGE_CAP_CUTOFF:
        return "Large Cap"
    if market_cap >= _MID_CAP_CUTOFF:
        return "Mid Cap"
    return "Small Cap"


def price_position_bucket(stage: str) -> str:
    return {
        "Fundamental Change": "Consolidating",
        "Quiet Accumulation": "Consolidating",
        "Volume Expansion": "Near Breakout",
        "Breakout": "Breakout",
        "Momentum": "Extended",
        "Extended": "Extended",
    }.get(stage, "Consolidating")


def profit_growth_bucket(profit_yoy_pct: float | None) -> str:
    if profit_yoy_pct is None:
        return "Unknown"
    if profit_yoy_pct > 100:
        return ">100%"
    if profit_yoy_pct > 50:
        return ">50%"
    if profit_yoy_pct > 20:
        return ">20%"
    return "<20%"
