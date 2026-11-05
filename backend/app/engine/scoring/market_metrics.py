"""Derives return/consolidation/volume metrics for one symbol from the free
NSE bhavcopy panel (data.nse_universe). Pure function of price/volume
history — no fundamentals, no network calls (the panel is already built).
"""
from dataclasses import dataclass

import pandas as pd


@dataclass
class MarketMetrics:
    available: bool
    current_price: float | None = None
    change_1w_pct: float | None = None
    change_1m_pct: float | None = None
    change_3m_pct: float | None = None
    change_6m_pct: float | None = None
    dist_from_52w_high_pct: float | None = None   # 0 = at high, negative = below it
    consolidation_range_20d_pct: float | None = None  # (high-low)/low over last 20 sessions
    volume_ratio_20d: float | None = None
    volume_ratio_50d: float | None = None
    sustained_volume_days: int | None = None       # of last 10 sessions, how many were >=1.5x 20d avg
    deliv_pct_recent_avg: float | None = None       # avg delivery % over last 10 sessions
    deliv_pct_prior_avg: float | None = None        # avg delivery % over the 10 sessions before that
    history_days: int = 0


def _pct_change(close: pd.Series, back: int) -> float | None:
    if len(close) <= back:
        return None
    return float((close.iloc[-1] - close.iloc[-1 - back]) / close.iloc[-1 - back] * 100)


def compute(history: pd.DataFrame) -> MarketMetrics:
    """history: OHLCV DataFrame shaped like data.nse_universe.symbol_price_history
    (DatetimeIndex, columns Open/High/Low/Close/Volume), ascending by date."""
    if history is None or history.empty or len(history) < 5:
        return MarketMetrics(available=False, history_days=0 if history is None else len(history))

    close = history["Close"]
    volume = history["Volume"]
    price_now = float(close.iloc[-1])

    change_1w = _pct_change(close, 5)
    change_1m = _pct_change(close, 21)
    change_3m = _pct_change(close, 63)
    change_6m = _pct_change(close, 126)

    window_high = float(close.tail(252).max())
    dist_52w_high = (price_now - window_high) / window_high * 100 if window_high else None

    consolidation = None
    if len(close) >= 20:
        recent20 = close.tail(20)
        lo = float(recent20.min())
        if lo > 0:
            consolidation = float((recent20.max() - lo) / lo * 100)

    vol_avg_20 = float(volume.tail(20).mean()) if len(volume) >= 20 else None
    vol_avg_50 = float(volume.tail(50).mean()) if len(volume) >= 50 else None
    vol_now = float(volume.iloc[-1])
    volume_ratio_20d = vol_now / vol_avg_20 if vol_avg_20 else None
    volume_ratio_50d = vol_now / vol_avg_50 if vol_avg_50 else None

    sustained_days = None
    if vol_avg_20 and vol_avg_20 > 0 and len(volume) >= 20:
        recent10 = volume.tail(10)
        sustained_days = int((recent10 >= 1.5 * vol_avg_20).sum())

    deliv_recent_avg = None
    deliv_prior_avg = None
    if "DelivPct" in history.columns and len(history) >= 20:
        deliv = history["DelivPct"].dropna()
        if len(deliv) >= 20:
            deliv_recent_avg = float(deliv.tail(10).mean())
            deliv_prior_avg = float(deliv.tail(20).head(10).mean())

    return MarketMetrics(
        available=True,
        current_price=price_now,
        change_1w_pct=change_1w,
        change_1m_pct=change_1m,
        change_3m_pct=change_3m,
        change_6m_pct=change_6m,
        dist_from_52w_high_pct=dist_52w_high,
        consolidation_range_20d_pct=consolidation,
        volume_ratio_20d=volume_ratio_20d,
        volume_ratio_50d=volume_ratio_50d,
        sustained_volume_days=sustained_days,
        deliv_pct_recent_avg=deliv_recent_avg,
        deliv_pct_prior_avg=deliv_prior_avg,
        history_days=len(history),
    )
