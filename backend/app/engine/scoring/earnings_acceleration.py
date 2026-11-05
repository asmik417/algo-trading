"""Pillar A — Earnings Acceleration (25 pts).

Rewards CHANGE IN TRAJECTORY, not just high growth. Revenue +50%/Profit +200%
must score much higher than Revenue +50%/Profit +55% — so every component is
built around the *gap* between profit and revenue growth (a proxy for margin
expansion / operating leverage kicking in), not growth in isolation.
"""
from app.engine.scoring.common import PillarResult, combine_components, pct_growth, scale

MAX_POINTS = 25


def score(quarterly: list[dict] | None, info: dict | None = None) -> PillarResult:
    """quarterly: chronologically ascending list of
    {"period": str, "revenue": float|None, "net_income": float|None, "eps": float|None}
    (most recent quarter last). info: yfinance .info snapshot, used only as a
    fallback when a full quarterly series isn't available."""
    quarterly = quarterly or []
    info = info or {}

    latest = quarterly[-1] if len(quarterly) >= 1 else None
    prev_q = quarterly[-2] if len(quarterly) >= 2 else None
    yoy_base = quarterly[-5] if len(quarterly) >= 5 else None
    prior_yoy_base = quarterly[-6] if len(quarterly) >= 6 else None

    revenue_yoy = pct_growth(latest["revenue"], yoy_base["revenue"]) if latest and yoy_base else None
    profit_yoy = pct_growth(latest["net_income"], yoy_base["net_income"]) if latest and yoy_base else None
    eps_yoy = pct_growth(latest["eps"], yoy_base["eps"]) if latest and yoy_base else None
    revenue_qoq = pct_growth(latest["revenue"], prev_q["revenue"]) if latest and prev_q else None
    profit_qoq = pct_growth(latest["net_income"], prev_q["net_income"]) if latest and prev_q else None

    prior_profit_yoy = (
        pct_growth(prev_q["net_income"], prior_yoy_base["net_income"])
        if prev_q and prior_yoy_base else None
    )

    # Fall back to yfinance's own trailing growth snapshot when we don't have
    # a usable quarterly series at all (e.g. company doesn't report the
    # breakdown yfinance needs, or is newly listed).
    if profit_yoy is None and info.get("earningsQuarterlyGrowth") is not None:
        profit_yoy = info["earningsQuarterlyGrowth"] * 100
    if revenue_yoy is None and info.get("revenueGrowth") is not None:
        revenue_yoy = info["revenueGrowth"] * 100

    positives, risks = [], []

    # Component A — growth quality: profit magnitude + profit-vs-revenue gap
    comp_a = None
    if profit_yoy is not None:
        magnitude = scale(profit_yoy, 0, 100)
        if revenue_yoy is not None:
            gap = profit_yoy - revenue_yoy
            quality = scale(gap, -20, 150)
            combined = 0.5 * magnitude + 0.5 * quality
            if gap > 50:
                positives.append(f"Profit growth ({profit_yoy:.0f}%) is far outpacing revenue growth ({revenue_yoy:.0f}%) — margin expansion, not just volume.")
        else:
            combined = magnitude
        comp_a = combined * 12
        if profit_yoy < 0:
            comp_a = min(comp_a, 2)
            risks.append(f"Net profit declined YoY ({profit_yoy:.0f}%).")

    # Component B — EPS acceleration
    comp_b = None
    if eps_yoy is not None:
        comp_b = scale(eps_yoy, 0, 100) * 7
        if eps_yoy < 0:
            comp_b = min(comp_b, 1)
        elif eps_yoy > 50:
            positives.append(f"EPS growth of {eps_yoy:.0f}% YoY.")

    # Component C — trajectory change: is the YoY growth rate itself accelerating?
    comp_c = None
    if profit_yoy is not None and prior_profit_yoy is not None:
        accel = profit_yoy - prior_profit_yoy
        comp_c = scale(accel, -20, 100) * 6
        if accel > 30:
            positives.append(f"Earnings growth is accelerating: YoY profit growth moved from {prior_profit_yoy:.0f}% to {profit_yoy:.0f}%.")

    pillar_score, coverage = combine_components(
        [(comp_a, 12), (comp_b, 7), (comp_c, 6)], MAX_POINTS
    )

    return PillarResult(
        score=pillar_score,
        max_points=MAX_POINTS,
        available=pillar_score is not None,
        details={
            "revenue_yoy_pct": revenue_yoy,
            "profit_yoy_pct": profit_yoy,
            "eps_yoy_pct": eps_yoy,
            "revenue_qoq_pct": revenue_qoq,
            "profit_qoq_pct": profit_qoq,
            "prior_quarter_profit_yoy_pct": prior_profit_yoy,
            "data_coverage": coverage,
        },
        positives=positives,
        risks=risks,
    )
