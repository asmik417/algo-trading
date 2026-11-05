"""Combines the six pillars into the final 0-100 Emerging Opportunity Score,
plus stage/signal classification. Pure and deterministic — no LLM calls here.
Weights are an argument (a profile's pillar weights); when omitted they
fall back to config.EMERGING_SCORE_WEIGHTS.
"""
from dataclasses import dataclass, field

import pandas as pd

from app.engine import config
from app.engine.scoring import earnings_acceleration, fundamental_quality, price_position, signal, stage, technical_setup, valuation, volume
from app.engine.scoring.common import PillarResult
from app.engine.scoring.market_metrics import MarketMetrics, compute as compute_market_metrics

PILLAR_ORDER = [
    ("earnings_acceleration", "Earnings Acceleration"),
    ("fundamental_quality", "Fundamental Quality"),
    ("early_price_position", "Early Price Position"),
    ("volume_accumulation", "Volume / Accumulation"),
    ("technical_setup", "Technical Setup"),
    ("valuation", "Valuation"),
]


@dataclass
class CandidateScore:
    symbol: str
    total_score: float | None
    data_coverage: float
    pillars: dict = field(default_factory=dict)     # key -> PillarResult
    market: MarketMetrics = None
    stage: str = "Fundamental Change"
    signal: str = "🔴 Weak / Invalidated"
    positives: list = field(default_factory=list)
    risks: list = field(default_factory=list)
    profit_yoy_pct: float | None = None
    current_price: float | None = None
    market_cap: float | None = None
    sector: str | None = None


def weighted_total(pillars: dict[str, PillarResult], weights: dict | None = None) -> tuple[float | None, float]:
    """0-100 score from pillar results under the given weights, renormalised over the
    pillars that are available. Each pillar contributes (score / max_points) x weight,
    so weights need not match the pillars' internal point scales.
    Returns (total_score or None, data_coverage as a fraction of total weight)."""
    weights = weights or config.EMERGING_SCORE_WEIGHTS
    total_weight = sum(float(weights.get(k, 0)) for k in pillars)
    available = [
        (p.score / p.max_points, float(weights.get(key, 0)))
        for key, p in pillars.items()
        if p.available and p.score is not None and p.max_points
    ]
    avail_weight = sum(w for _, w in available)
    if not available or avail_weight <= 0 or total_weight <= 0:
        return None, 0.0
    earned = sum(frac * w for frac, w in available)
    return (earned / avail_weight) * 100, avail_weight / total_weight


def evaluate(
    symbol: str,
    history: pd.DataFrame,
    info: dict | None,
    quarterly: list[dict] | None = None,
    cashflow_trend: list[dict] | None = None,
    weights: dict | None = None,
) -> CandidateScore:
    market = compute_market_metrics(history)

    earn = earnings_acceleration.score(quarterly, info)
    fq = fundamental_quality.score(info, cashflow_trend)
    profit_yoy = earn.details.get("profit_yoy_pct")
    pp = price_position.score(market, profit_yoy)
    vol = volume.score(market)
    tech = technical_setup.score(history)
    val = valuation.score(info, profit_yoy, market.change_6m_pct if market.available else None)

    pillars: dict[str, PillarResult] = {
        "earnings_acceleration": earn,
        "fundamental_quality": fq,
        "early_price_position": pp,
        "volume_accumulation": vol,
        "technical_setup": tech,
        "valuation": val,
    }

    total_score, data_coverage = weighted_total(pillars, weights)

    stage_inputs = stage.StageInputs(
        change_3m_pct=pp.details.get("change_3m_pct"),
        dist_from_52w_high_pct=pp.details.get("dist_from_52w_high_pct"),
        volume_ratio_20d=vol.details.get("volume_ratio_20d"),
        sustained_volume_days=vol.details.get("sustained_volume_days_of_10"),
        rsi=tech.details.get("rsi"),
        macd_signal=tech.details.get("macd_signal"),
        earnings_score_frac=(earn.score / earn.max_points) if earn.available else None,
        technical_score_frac=(tech.score / tech.max_points) if tech.available else None,
    )
    stg = stage.classify(stage_inputs)
    tech_frac = (tech.score / tech.max_points) if tech.available else None
    sig = signal.classify(total_score, stg, tech_frac)

    positives, risks = [], []
    for p in pillars.values():
        positives.extend(p.positives)
        risks.extend(p.risks)

    info = info or {}
    return CandidateScore(
        symbol=symbol,
        total_score=total_score,
        data_coverage=data_coverage,
        pillars=pillars,
        market=market,
        stage=stg,
        signal=sig,
        positives=positives,
        risks=risks,
        profit_yoy_pct=profit_yoy,
        current_price=market.current_price if market.available else info.get("currentPrice"),
        market_cap=info.get("marketCap"),
        sector=info.get("sector"),
    )
