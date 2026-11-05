"""Classifies a candidate into one of six setup stages. Not every stock
passes through every stage — this picks the single best-evidenced stage
given whatever signals are actually available.

Fundamental Change -> Quiet Accumulation -> Volume Expansion -> Breakout -> Momentum -> Extended
"""
from dataclasses import dataclass


@dataclass
class StageInputs:
    change_3m_pct: float | None
    dist_from_52w_high_pct: float | None
    volume_ratio_20d: float | None
    sustained_volume_days: int | None
    rsi: float | None
    macd_signal: str | None
    earnings_score_frac: float | None   # earnings-acceleration pillar score / max, 0..1
    technical_score_frac: float | None  # technical-setup pillar score / max, 0..1


STAGES = [
    "Fundamental Change",
    "Quiet Accumulation",
    "Volume Expansion",
    "Breakout",
    "Momentum",
    "Extended",
]


def classify(s: StageInputs) -> str:
    near_high = s.dist_from_52w_high_pct is not None and s.dist_from_52w_high_pct >= -8
    off_high = s.dist_from_52w_high_pct is not None and s.dist_from_52w_high_pct <= -10
    big_runup = s.change_3m_pct is not None and s.change_3m_pct >= 80
    overbought = s.rsi is not None and s.rsi >= 78
    strong_volume = s.volume_ratio_20d is not None and s.volume_ratio_20d >= 1.8
    sustained = s.sustained_volume_days is not None and s.sustained_volume_days >= 2
    mild_volume = s.volume_ratio_20d is not None and s.volume_ratio_20d >= 1.15
    bullish_macd = s.macd_signal in ("BULLISH_CROSSOVER", "BULLISH")

    # Extended — already ran a long way and/or technically overbought; no longer "early".
    if big_runup or overbought:
        return "Extended"

    # Momentum — already broke out and is trending, run-up is meaningful but not yet extreme.
    if near_high and bullish_macd and s.change_3m_pct is not None and 30 <= s.change_3m_pct < 80:
        return "Momentum"

    # Breakout — near/at resistance with real volume confirmation.
    if near_high and (strong_volume or sustained) and bullish_macd:
        return "Breakout"

    # Volume Expansion — participation clearly picking up, but price hasn't broken out yet.
    if off_high and (strong_volume or sustained):
        return "Volume Expansion"

    # Quiet Accumulation — mild volume pickup with a constructive technical/earnings backdrop.
    if mild_volume and (s.earnings_score_frac or 0) >= 0.4:
        return "Quiet Accumulation"

    # Fundamental Change — the earnings signal is there but the market hasn't reacted at all yet.
    if (s.earnings_score_frac or 0) >= 0.5:
        return "Fundamental Change"

    return "Quiet Accumulation" if mild_volume else "Fundamental Change"
