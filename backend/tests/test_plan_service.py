"""Step 5: the deterministic trade plan — entries, stop, target, horizon, exit date and notes.
Synthetic OHLCV only.
"""
import numpy as np
import pandas as pd
import pytest

from app.engine.data.indicators import compute_indicators
from app.engine.params import ScreenParams
from app.services import plan_service
from app.services.plan_service import build_plan, rupees


def hist(closes, spread=0.01, end="2026-11-04"):
    closes = np.asarray(closes, dtype=float)
    idx = pd.bdate_range(end=end, periods=len(closes))
    return pd.DataFrame({"Open": closes, "High": closes * (1 + spread), "Low": closes * (1 - spread),
                         "Close": closes, "Volume": 100_000}, index=idx)


UPTREND = hist(np.linspace(100, 160, 120) + np.sin(np.arange(120)) * 1.5)
DEFAULT = ScreenParams.from_dict({})


def test_rules_match_spec():
    plan = build_plan(UPTREND, "Quiet Accumulation", DEFAULT, "2026-11-04")
    ind = compute_indicators(UPTREND)
    close, atr = float(UPTREND["Close"].iloc[-1]), ind["atr"]
    low20 = float(UPTREND["Low"].tail(20).min())

    assert plan.entry_aggressive == round(close, 2)
    assert plan.entry_optimal == round(ind["ema20"], 2)            # uptrend: EMA20 below close
    assert plan.entry_conservative == round(ind["ema50"], 2)       # EMA50 below EMA20
    expected_stop = max(min(close - 2.0 * atr, 0.98 * low20), 0.80 * close)
    assert plan.stop_loss == pytest.approx(expected_stop, abs=0.01)
    assert plan.target == pytest.approx(close + 2.0 * (close - expected_stop), abs=0.02)
    assert plan.risk_reward == 2.0
    assert plan.entry_conservative < plan.entry_optimal < plan.entry_aggressive < plan.target
    assert plan.stop_loss < plan.entry_conservative


def test_entries_fall_back_to_atr_when_emas_are_above_price():
    down = hist(np.linspace(160, 100, 120))
    plan = build_plan(down, "Fundamental Change", DEFAULT, "2026-11-04")
    atr = compute_indicators(down)["atr"]
    close = float(down["Close"].iloc[-1])
    assert plan.entry_optimal == pytest.approx(max(close - 0.5 * atr, plan.stop_loss), abs=0.01)
    assert plan.stop_loss < plan.entry_conservative < plan.entry_optimal


def test_entries_never_at_or_below_stop():
    # Parabolic run: EMA50 far below the 20% stop floor.
    rocket = hist(100 * 1.02 ** np.arange(120), spread=0.002)
    plan = build_plan(rocket, "Momentum", DEFAULT, "2026-11-04")
    assert plan.stop_loss == pytest.approx(0.80 * plan.entry_aggressive, abs=0.01)
    assert plan.stop_loss < plan.entry_conservative < plan.entry_optimal <= plan.entry_aggressive


@pytest.mark.parametrize("stage,pref,expected", [
    ("Fundamental Change", "Medium (1-3 months)", 60),
    ("Quiet Accumulation", "Short (2-6 weeks)", 30),
    ("Breakout", "Long (3-6 months)", 40),
    ("Extended", "Short (2-6 weeks)", 10),      # 6 -> clamped to 10
    ("Fundamental Change", "Long (3-6 months)", 96),
])
def test_horizon(stage, pref, expected):
    assert plan_service.horizon_days_for(stage, pref) == expected


def test_exit_date_counts_business_days():
    assert plan_service.exit_date_after("2026-11-04", 1) == "2026-11-05"
    assert plan_service.exit_date_after("2026-11-06", 1) == "2026-11-09"   # Fri + 1 -> Mon
    assert plan_service.exit_date_after("2026-11-04", 50) == "2027-01-13"
    plan = build_plan(UPTREND, "Quiet Accumulation", DEFAULT, "2026-11-04")
    assert (plan.horizon_days, plan.planned_exit_date) == (50, "2027-01-13")


def test_params_drive_stop_and_target():
    tight = ScreenParams.from_dict({"stop_atr_mult": 0.5, "target_rr": 3.0})
    a = build_plan(UPTREND, "Breakout", DEFAULT, "2026-11-04")
    b = build_plan(UPTREND, "Breakout", tight, "2026-11-04")
    assert b.risk_reward == 3.0
    assert (b.target - b.entry_aggressive) == pytest.approx(3.0 * (b.entry_aggressive - b.stop_loss), abs=0.03)
    assert a.stop_loss <= b.stop_loss  # min(close - k*ATR, 0.98*low20) never gets wider with a smaller k


def test_notes_mention_real_levels():
    plan = build_plan(UPTREND, "Quiet Accumulation", DEFAULT, "2026-11-04")
    assert rupees(plan.entry_optimal) in plan.timing_note
    assert plan.exit_note == (f"Book profit at {rupees(plan.target)} or exit on a close below {rupees(plan.stop_loss)}. "
                              "Re-assess on 13 Jan 2027 if neither is hit.")
    assert plan.disclaimer == "This plan is rules-based and may vary with news and live market updates. Paper trading only."
    for stage in plan_service.BASE_HORIZON_DAYS:
        assert "₹" in build_plan(UPTREND, stage, DEFAULT, "2026-11-04").timing_note


def test_short_or_broken_history_gives_no_plan():
    assert build_plan(hist([100.0] * 10), "Breakout", DEFAULT, "2026-11-04") is None
    assert build_plan(hist([100.0] * 60, spread=0.0), "Breakout", DEFAULT, "2026-11-04") is None  # ATR 0
    assert build_plan(pd.DataFrame(), "Breakout", DEFAULT, "2026-11-04") is None


def test_rupee_format():
    assert rupees(1234.5) == "₹1,234.50"
    assert rupees(1210) == "₹1,210"
    assert rupees(140000) == "₹1,40,000"
    assert rupees(12345.6) == "₹12,345.60"
    assert rupees(99.999) == "₹100"
