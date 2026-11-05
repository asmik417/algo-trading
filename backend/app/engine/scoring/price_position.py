"""Pillar C — Early Price Position (15 pts).

This is where "find it early" actually gets enforced: strong fundamentals
sitting on a flat/consolidating chart score high; strong fundamentals that
have already produced a big rally score low, even if the setup otherwise
looks identical. Built on top of the Fundamental-Price Disconnect metric
plus a direct run-up/consolidation check.
"""
from app.engine.scoring import disconnect
from app.engine.scoring.common import PillarResult, combine_components, scale
from app.engine.scoring.market_metrics import MarketMetrics

MAX_POINTS = 15


def score(market: MarketMetrics, fundamental_growth_pct: float | None) -> PillarResult:
    positives, risks = [], []

    disc = disconnect.compute(fundamental_growth_pct, market.change_3m_pct if market.available else None)
    comp_disc = disc.score_0_1 * 9 if disc.available else None
    if disc.available:
        if disc.label == "Strong":
            positives.append("Fundamental improvement has barely shown up in the price yet.")
        elif disc.label == "Priced In":
            risks.append("Price has already moved a lot relative to the fundamental improvement — largely priced in.")

    comp_runup = None
    comp_consol = None
    if market.available:
        if market.change_3m_pct is not None:
            run_up_penalty = scale(max(market.change_3m_pct, 0), 20, 150, reverse=True)
            comp_runup = run_up_penalty * 4
            if market.change_3m_pct > 100:
                risks.append(f"Stock already up {market.change_3m_pct:.0f}% over 3 months — no longer early.")
        if market.consolidation_range_20d_pct is not None:
            consolidation_bonus = scale(market.consolidation_range_20d_pct, 10, 40, reverse=True)
            comp_consol = consolidation_bonus * 2
            if market.consolidation_range_20d_pct < 12:
                positives.append("Price is tightly consolidating — a base, not a breakout that already ran.")

    pillar_score, coverage = combine_components(
        [(comp_disc, 9), (comp_runup, 4), (comp_consol, 2)], MAX_POINTS
    )

    return PillarResult(
        score=pillar_score,
        max_points=MAX_POINTS,
        available=pillar_score is not None,
        details={
            "disconnect_label": disc.label,
            "disconnect_score_0_1": disc.score_0_1,
            "change_1w_pct": market.change_1w_pct,
            "change_1m_pct": market.change_1m_pct,
            "change_3m_pct": market.change_3m_pct,
            "change_6m_pct": market.change_6m_pct,
            "dist_from_52w_high_pct": market.dist_from_52w_high_pct,
            "consolidation_range_20d_pct": market.consolidation_range_20d_pct,
            "data_coverage": coverage,
        },
        positives=positives,
        risks=risks,
    )
