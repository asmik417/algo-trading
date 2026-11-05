"""Pillar E — Technical Setup (15 pts).

Reuses the existing data.indicators.compute_indicators() (same RSI/MACD/EMA/
Bollinger/ATR/volume calculations the Technical agent already relies on) so
this pillar reads the same indicators the rest of the app shows, just scored
deterministically instead of handed to an LLM. Technicals alone never make a
stock an Emerging Opportunity — this is one of six pillars, not the gate.
"""
import re

import pandas as pd

from app.engine.data.indicators import compute_indicators
from app.engine.scoring.common import PillarResult, combine_components, scale

MAX_POINTS = 15

_TREND_SCORE = {
    "STRONG_UPTREND": 1.0,
    "ABOVE_200EMA (bullish bias)": 0.75,
    "UPTREND": 0.65,
    "BELOW_200EMA (bearish bias)": 0.25,
    "DOWNTREND": 0.15,
    "STRONG_DOWNTREND": 0.0,
}

_MACD_SCORE = {
    "BULLISH_CROSSOVER": 1.0,
    "BULLISH": 0.7,
    "BEARISH": 0.2,
    "BEARISH_CROSSOVER": 0.0,
}


def _rsi_score(rsi: float) -> float:
    if rsi >= 80:
        return 0.05   # extremely overextended — penalize per spec
    if rsi >= 70:
        return 0.3
    if 50 <= rsi < 70:
        return 1.0
    if 40 <= rsi < 50:
        return 0.6
    return 0.25


def _bb_score(bb_position: str) -> float:
    if bb_position.startswith("UPPER_BAND"):
        return 0.4   # already at/above resistance — extended, not a fresh breakout setup
    if bb_position.startswith("LOWER_BAND"):
        return 0.2
    m = re.search(r"(\d+)%", bb_position)
    if m:
        return min(1.0, int(m.group(1)) / 85)   # approaching the upper band = approaching resistance
    return 0.5


def score(history: pd.DataFrame) -> PillarResult:
    if history is None or len(history) < 30:
        return PillarResult(score=None, max_points=MAX_POINTS, available=False, details={})

    try:
        ind = compute_indicators(history)
    except Exception:
        return PillarResult(score=None, max_points=MAX_POINTS, available=False, details={})

    positives, risks = [], []

    comp_trend = _TREND_SCORE.get(ind["ema_trend"], 0.5) * 6
    if ind["ema_trend"] in ("STRONG_UPTREND", "ABOVE_200EMA (bullish bias)"):
        positives.append(f"Trend: {ind['ema_trend'].replace('_', ' ').title()}.")
    elif ind["ema_trend"] in ("STRONG_DOWNTREND", "BELOW_200EMA (bearish bias)"):
        risks.append("Price is below its key moving averages — weak trend structure.")

    comp_rsi = _rsi_score(ind["rsi"]) * 4
    if ind["rsi"] >= 80:
        risks.append(f"RSI at {ind['rsi']:.0f} — extremely overextended.")

    comp_macd = _MACD_SCORE.get(ind["macd_signal"], 0.4) * 3

    comp_bb = _bb_score(ind["bb_position"]) * 2

    pillar_score, coverage = combine_components(
        [(comp_trend, 6), (comp_rsi, 4), (comp_macd, 3), (comp_bb, 2)], MAX_POINTS
    )

    return PillarResult(
        score=pillar_score,
        max_points=MAX_POINTS,
        available=pillar_score is not None,
        details={
            "rsi": ind["rsi"],
            "rsi_signal": ind["rsi_signal"],
            "macd_signal": ind["macd_signal"],
            "ema_trend": ind["ema_trend"],
            "ema20": ind["ema20"],
            "ema50": ind["ema50"],
            "ema200": ind["ema200"],
            "bb_position": ind["bb_position"],
            "data_coverage": coverage,
        },
        positives=positives,
        risks=risks,
    )
