"""Cutting price histories at a scan date (the no-look-ahead boundary) and reading the bars after it.
Histories are OHLCV DataFrames with a sorted DatetimeIndex (as market_data.all_histories returns them).
"""
import pandas as pd


def upto(history: pd.DataFrame, day) -> pd.DataFrame:
    """Bars on or before `day`: everything the engine may see on that scan date."""
    return history.loc[history.index <= pd.Timestamp(day)]


def upto_all(histories: dict[str, pd.DataFrame], day) -> dict[str, pd.DataFrame]:
    out = {}
    for sym, h in histories.items():
        cut = upto(h, day)
        if not cut.empty:
            out[sym] = cut
    return out


def after(history: pd.DataFrame, day, until) -> pd.DataFrame:
    """Bars strictly after `day`, up to and including `until`."""
    idx = history.index
    return history.loc[(idx > pd.Timestamp(day)) & (idx <= pd.Timestamp(until))]


def avg_turnover_lacs(history: pd.DataFrame, rows: int = 20) -> float | None:
    if "TurnoverLacs" not in history or len(history) < rows:
        return None
    value = float(history["TurnoverLacs"].tail(rows).mean())
    return value if value == value else None  # NaN -> None
