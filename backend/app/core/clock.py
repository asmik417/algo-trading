"""Time helpers so every stored timestamp has the same ISO-8601 UTC shape ("2026-11-05T09:00:00Z").
Market dates are separate: plain ISO trading days ("2026-11-04").
"""
from datetime import datetime, timezone


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
