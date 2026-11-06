"""Deterministic loss-pattern tags for losing simulated trades, using the Loss Analysis tag vocabulary.
Every rule that matches is applied; a loss matching none is tagged "other".
"""
import pandas as pd
import ta

from app.engine.backtest.simulate import Trade

LOW_LIQUIDITY_LACS = 100.0  # ₹1 crore average daily turnover


def ema20_on(history: pd.DataFrame, day) -> float | None:
    upto = history.loc[history.index <= pd.Timestamp(day), "Close"]
    if len(upto) < 20:
        return None
    value = float(ta.trend.EMAIndicator(upto.astype(float), window=20).ema_indicator().iloc[-1])
    return value if value == value else None


def tag_loss(trade: Trade, history: pd.DataFrame) -> list[str]:
    """Tags for one closed losing trade. `history` is the symbol's full price history (analysis after the fact)."""
    entry, stop = trade.entry_price, trade.stop_loss
    closes = history["Close"]
    tags: list[str] = []

    if trade.exit_reason == "stop_hit" and trade.days_held <= 5 and trade.exit_date:
        later = closes.loc[(closes.index > pd.Timestamp(trade.exit_date))
                           & (closes.index < pd.Timestamp(trade.planned_exit_date))]
        if (later > entry).any():
            tags.append("stop_too_tight")
    ema = ema20_on(history, trade.entry_date)
    if ema and (entry - ema) / ema > 0.08:
        tags.append("bought_extended")
    if trade.nifty_pct is not None and trade.nifty_pct <= -3:
        tags.append("whole_market_fell")
    if trade.exit_reason == "horizon_closed" and trade.mfe_pct is not None and entry > 0:
        target_dist_pct = (trade.target - entry) / entry * 100
        if target_dist_pct > 0 and trade.mfe_pct >= target_dist_pct / 2:
            tags.append("held_too_long")
    risk = entry - stop
    first3 = closes.loc[closes.index > pd.Timestamp(trade.entry_date)].head(3)
    if risk > 0 and not first3.empty and (entry - float(first3.min())) >= risk / 2:
        tags.append("bad_entry_timing")
    if trade.avg_turnover_lacs is not None and trade.avg_turnover_lacs < LOW_LIQUIDITY_LACS:
        tags.append("low_liquidity")
    return tags or ["other"]


def tag_losses(trades: list[Trade], histories: dict[str, pd.DataFrame]) -> None:
    """Set .tags on every closed losing trade (in place); other trades keep no tags."""
    for t in trades:
        t.tags = tag_loss(t, histories[t.symbol]) if t.closed and t.pnl < 0 else []
