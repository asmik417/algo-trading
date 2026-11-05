"""Pillar D — Volume / Accumulation (15 pts).

A single volume spike is noise. This pillar specifically rewards *sustained*
elevated participation (multiple above-average sessions, not one outlier)
and rising delivery % (genuine buying/holding vs pure intraday churn).
"""
from app.engine.scoring.common import PillarResult, combine_components, scale
from app.engine.scoring.market_metrics import MarketMetrics

MAX_POINTS = 15


def score(market: MarketMetrics) -> PillarResult:
    if not market.available:
        return PillarResult(score=None, max_points=MAX_POINTS, available=False, details={})

    positives, risks = [], []

    comp_ratio = None
    if market.volume_ratio_20d is not None:
        comp_ratio = scale(market.volume_ratio_20d, 1.0, 3.0) * 6
        if market.volume_ratio_20d >= 2.0:
            positives.append(f"Volume running at {market.volume_ratio_20d:.1f}x its 20-day average.")

    comp_sustained = None
    if market.sustained_volume_days is not None:
        comp_sustained = scale(market.sustained_volume_days, 1, 6) * 5
        if market.sustained_volume_days == 0:
            risks.append("No sustained above-average volume yet — participation hasn't picked up.")
        elif market.sustained_volume_days >= 3:
            positives.append(f"{market.sustained_volume_days} of the last 10 sessions saw elevated volume — not a one-off spike.")

    comp_deliv = None
    if market.deliv_pct_recent_avg is not None and market.deliv_pct_prior_avg is not None:
        deliv_change = market.deliv_pct_recent_avg - market.deliv_pct_prior_avg
        comp_deliv = scale(deliv_change, -5, 15) * 4
        if deliv_change > 5:
            positives.append(f"Delivery % rising ({market.deliv_pct_prior_avg:.0f}% → {market.deliv_pct_recent_avg:.0f}%) — looks like genuine accumulation, not just trading churn.")

    pillar_score, coverage = combine_components(
        [(comp_ratio, 6), (comp_sustained, 5), (comp_deliv, 4)], MAX_POINTS
    )

    return PillarResult(
        score=pillar_score,
        max_points=MAX_POINTS,
        available=pillar_score is not None,
        details={
            "volume_ratio_20d": market.volume_ratio_20d,
            "volume_ratio_50d": market.volume_ratio_50d,
            "sustained_volume_days_of_10": market.sustained_volume_days,
            "deliv_pct_recent_avg": market.deliv_pct_recent_avg,
            "deliv_pct_prior_avg": market.deliv_pct_prior_avg,
            "data_coverage": coverage,
        },
        positives=positives,
        risks=risks,
    )
