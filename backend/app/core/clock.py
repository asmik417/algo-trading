"""Time helpers so every stored timestamp has the same ISO-8601 UTC shape ("2026-11-05T09:00:00Z").
Market dates are separate: plain ISO trading days ("2026-11-04").
"""
from datetime import datetime, timezone
from typing import Protocol

from zoneinfo import ZoneInfo


class Clock(Protocol):
    """Small injection boundary for deterministic tests and replayable paper runs."""

    def utc_now(self) -> datetime:
        ...

    def trading_day(self) -> str:
        ...


class SystemClock:
    """Production clock; market dates follow Asia/Kolkata trading calendar conventions."""

    def utc_now(self) -> datetime:
        return datetime.now(timezone.utc)

    def trading_day(self) -> str:
        return self.utc_now().astimezone(ZoneInfo("Asia/Kolkata")).date().isoformat()


SYSTEM_CLOCK = SystemClock()


def utc_now_iso() -> str:
    return SYSTEM_CLOCK.utc_now().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def trading_day_utc() -> str:
    return SYSTEM_CLOCK.trading_day()
