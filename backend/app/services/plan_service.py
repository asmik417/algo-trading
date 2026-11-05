"""Deterministic trade plan for a stock: three entry levels, stop-loss, target, holding horizon and exit date.
Rules are in docs/TASKS_BACKEND.md Step 5; the notes are plain English built from the computed rupee levels.
"""
import math
from dataclasses import asdict, dataclass
from datetime import date

import numpy as np
import pandas as pd

from app.engine.data.indicators import compute_indicators
from app.engine.params import ScreenParams

DISCLAIMER = "This plan is rules-based and may vary with news and live market updates. Paper trading only."

BASE_HORIZON_DAYS = {
    "Fundamental Change": 60,
    "Quiet Accumulation": 50,
    "Volume Expansion": 35,
    "Breakout": 25,
    "Momentum": 20,
    "Extended": 10,
}
HORIZON_MULTIPLIER = {"Short": 0.6, "Medium": 1.0, "Long": 1.6}
MIN_HORIZON, MAX_HORIZON = 10, 130
MIN_HISTORY_ROWS = 20


@dataclass
class Plan:
    entry_aggressive: float
    entry_optimal: float
    entry_conservative: float
    stop_loss: float
    target: float
    risk_reward: float
    horizon_days: int
    planned_exit_date: str
    timing_note: str
    exit_note: str
    disclaimer: str = DISCLAIMER

    def to_dict(self) -> dict:
        return asdict(self)


# --- formatting --------------------------------------------------------------

def rupees(value: float) -> str:
    """₹ with Indian digit grouping: 1234.5 -> ₹1,234.50, 140000 -> ₹1,40,000; whole rupees drop the paise."""
    neg, value = value < 0, abs(round(value, 2))
    whole, paise = divmod(round(value * 100), 100)
    digits = str(whole)
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        digits = ",".join(([head] if head else []) + groups + [tail])
    text = f"₹{digits}" + (f".{paise:02d}" if paise else "")
    return f"-{text}" if neg else text


def display_date(iso: str) -> str:
    return date.fromisoformat(iso).strftime("%d %b %Y")


# --- rules -------------------------------------------------------------------

def horizon_days_for(stage: str, horizon_pref: str) -> int:
    base = BASE_HORIZON_DAYS.get(stage, BASE_HORIZON_DAYS["Volume Expansion"])
    mult = next((m for k, m in HORIZON_MULTIPLIER.items() if horizon_pref.startswith(k)), 1.0)
    return int(min(MAX_HORIZON, max(MIN_HORIZON, round(base * mult))))


def exit_date_after(trading_day: str, horizon_days: int) -> str:
    """trading_day + N business days (Mon-Fri; NSE holidays are not modelled)."""
    return str(np.busday_offset(np.datetime64(trading_day, "D"), horizon_days, roll="forward"))


def _finite(x) -> float | None:
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _timing_note(stage: str, close: float, optimal: float, conservative: float, chase: float) -> str:
    c, o, s, ch = rupees(close), rupees(optimal), rupees(conservative), rupees(chase)
    notes = {
        "Fundamental Change": (f"Early stage: the price has not reacted to the fundamentals yet. Build the position slowly "
                               f"near {o}, adding more near {s}; there is no need to buy at {c} in a hurry."),
        "Quiet Accumulation": (f"Accumulate on pullbacks toward {o} over the next 5-10 sessions; "
                               f"avoid chasing above {ch}."),
        "Volume Expansion": (f"Volume is picking up. Buy part near {c} and add on a dip toward {o}; "
                             f"skip it if it runs above {ch} without a pause."),
        "Breakout": (f"Breakout in progress: buy near {c} or on a retest of {o} within 3-5 sessions. "
                     f"A close back below {s} means the breakout failed."),
        "Momentum": f"Strong momentum: only buy on a pullback toward {o}; do not chase above {ch}.",
        "Extended": (f"Extended after a big run: wait for a pullback toward {s} or a fresh base before buying; "
                     f"buying at {c} carries extra risk."),
    }
    return notes.get(stage, f"Prefer entries near {o}; avoid chasing above {ch}.")


def build_plan(history: pd.DataFrame, stage: str, params: ScreenParams, trading_day: str) -> Plan | None:
    """Plan from the last row of `history` (OHLCV, oldest first). None when history is too short to plan."""
    if history is None or len(history) < MIN_HISTORY_ROWS:
        return None
    ind = compute_indicators(history)
    close = _finite(history["Close"].iloc[-1])
    atr = _finite(ind.get("atr"))
    if close is None or close <= 0 or atr is None or atr <= 0:
        return None
    ema20, ema50 = _finite(ind.get("ema20")), _finite(ind.get("ema50"))
    low_20d = float(history["Low"].tail(20).min())

    entry_aggressive = close
    entry_optimal = ema20 if ema20 is not None and ema20 < close else close - 0.5 * atr
    entry_conservative = ema50 if ema50 is not None and ema50 < entry_optimal else close - 1.5 * atr
    stop_loss = max(min(close - float(params.stop_atr_mult) * atr, 0.98 * low_20d), 0.80 * close)

    # Guard (not in the Step 5 rules): an entry at or below the stop would be stopped out on fill.
    # Lift such levels into the band between the stop and the level above them.
    if entry_optimal <= stop_loss:
        entry_optimal = stop_loss + 0.5 * (entry_aggressive - stop_loss)
    if entry_conservative <= stop_loss:
        entry_conservative = stop_loss + 0.5 * (entry_optimal - stop_loss)

    risk = entry_aggressive - stop_loss
    target_rr = float(params.target_rr)
    target = entry_aggressive + target_rr * risk
    horizon_days = horizon_days_for(stage, str(params.horizon))
    planned_exit = exit_date_after(trading_day, horizon_days)

    r2 = lambda v: round(float(v), 2)  # noqa: E731
    entry_aggressive, entry_optimal, entry_conservative = r2(entry_aggressive), r2(entry_optimal), r2(entry_conservative)
    stop_loss, target = r2(stop_loss), r2(target)

    return Plan(
        entry_aggressive=entry_aggressive,
        entry_optimal=entry_optimal,
        entry_conservative=entry_conservative,
        stop_loss=stop_loss,
        target=target,
        risk_reward=r2(target_rr),
        horizon_days=horizon_days,
        planned_exit_date=planned_exit,
        timing_note=_timing_note(stage, entry_aggressive, entry_optimal, entry_conservative, r2(close + atr)),
        exit_note=(f"Book profit at {rupees(target)} or exit on a close below {rupees(stop_loss)}. "
                   f"Re-assess on {display_date(planned_exit)} if neither is hit."),
    )
