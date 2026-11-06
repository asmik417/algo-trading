"""Scan dates for a backtest: weekly (last trading day of each ISO week) or daily, inside the requested range,
with the start clamped so enough history precedes the first scan.
"""
from collections.abc import Iterable
from datetime import date

import pandas as pd

MIN_HISTORY_DAYS = 250  # trading days of history required before the first scan


def scan_dates(trading_days: Iterable, start: date, end: date, frequency: str = "weekly",
               min_history: int = MIN_HISTORY_DAYS) -> tuple[date | None, list[pd.Timestamp]]:
    """(effective_start, scan dates). effective_start = max(start, the first day with `min_history` trading
    days before it). Returns (None, []) when the calendar is too short for even one scan."""
    days = sorted({pd.Timestamp(d).normalize() for d in trading_days})
    if len(days) <= min_history:
        return None, []
    effective_start = max(pd.Timestamp(start), days[min_history])
    in_range = [d for d in days if effective_start <= d <= pd.Timestamp(end)]
    if frequency == "daily":
        picked = in_range
    elif frequency == "weekly":
        last_of_week: dict[tuple[int, int], pd.Timestamp] = {}
        for d in in_range:
            iso = d.isocalendar()
            last_of_week[(iso[0], iso[1])] = d  # in_range is sorted, so the last write wins
        picked = sorted(last_of_week.values())
    else:
        raise ValueError(f"unknown frequency {frequency!r}")
    return effective_start.date(), picked
