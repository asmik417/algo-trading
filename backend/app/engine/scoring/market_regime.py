"""Whole-market condition used as a hard filter: how far Nifty 50's close is above/below its 50-day EMA on a day.
Pure; only Nifty bars on or before the day are used, so backtests never see later market moves.
"""
import pandas as pd
import ta

EMA_WINDOW = 50


def nifty_vs_ema50_pct(closes: pd.Series | None, day) -> float | None:
    """(close / EMA50 - 1) x 100 on the last Nifty session on or before `day`; None with fewer than 50 sessions."""
    if closes is None or closes.empty:
        return None
    upto = closes.loc[closes.index <= pd.Timestamp(day)].astype(float)
    if len(upto) < EMA_WINDOW:
        return None
    ema = float(ta.trend.EMAIndicator(upto, window=EMA_WINDOW).ema_indicator().iloc[-1])
    if not ema or ema != ema:
        return None
    return round((float(upto.iloc[-1]) / ema - 1) * 100, 4)
