"""Market filter (min_nifty_vs_ema50_pct): no new picks on a day Nifty 50 closes more than X% below its 50-day EMA.
The calculation, the hard filter in live runs / Explore / verdicts, backtests (per scan date, no look-ahead), the
Strategies form field. No network.
"""
import numpy as np
import pandas as pd
import pytest

from app.engine.params import DEFAULTS, PARAM_SPEC
from app.engine.scoring.market_regime import nifty_vs_ema50_pct
from app.services import backtest_service, market_data
from tests.test_backtest_service import END, OPEN_PARAMS, world  # noqa: F401  (fixture)
from tests.test_suggestion_runs import _profile, _run, market  # noqa: F401  (fixture)

MSG = "below its 50-day EMA, more than max 2%: no new picks today"


def nifty(values, end="2026-11-04"):
    return pd.Series(np.asarray(values, dtype=float), index=pd.bdate_range(end=end, periods=len(values)))


RISING = nifty(np.linspace(20000, 26000, 120))
FALLING = nifty(np.r_[np.full(100, 25000.0), np.linspace(25000, 22000, 20)])  # last close ~10% below EMA50


# --- the calculation ---------------------------------------------------------------------------------

def test_nifty_vs_ema50():
    assert nifty_vs_ema50_pct(RISING, "2026-11-04") > 0
    assert nifty_vs_ema50_pct(FALLING, "2026-11-04") < -5
    assert nifty_vs_ema50_pct(nifty([100.0] * 49), "2026-11-04") is None          # fewer than 50 sessions
    assert nifty_vs_ema50_pct(None, "2026-11-04") is None
    day = FALLING.index[100]                                                      # before the fall started
    later = FALLING.copy()
    later.iloc[101:] = 1.0                                                       # whatever happens afterwards...
    assert nifty_vs_ema50_pct(FALLING, day) == nifty_vs_ema50_pct(later, day) == pytest.approx(0.0, abs=1e-9)


def test_strategies_form_field():
    assert DEFAULTS["min_nifty_vs_ema50_pct"] == 0.0                              # off by default
    field = next(f for s in PARAM_SPEC if s["section"] == "Technicals" for f in s["fields"]
                 if f["key"] == "min_nifty_vs_ema50_pct")
    assert (field["type"], field["min"], field["max"]) == ("number", 0.0, 20.0) and "0 = off" in field["help"]


# --- live runs, Explore, verdict --------------------------------------------------------------------------

def test_falling_market_blocks_new_picks_live(client, market, monkeypatch):  # noqa: F811
    monkeypatch.setattr(market_data, "_nifty_closes", lambda: FALLING)
    pid = _profile(client, min_nifty_vs_ema50_pct=2.0)
    run = _run(client, pid)
    assert run["status"] == "done" and run["passed_size"] == 0
    assert client.get(f"/api/v1/profiles/{pid}/suggestions").json()["items"] == []
    d = client.post(f"/api/v1/stocks/GOODCO/analyze?profile_id={pid}").json()
    assert d["filters"]["passed"] is False and any(MSG in f for f in d["filters"]["failures"])
    assert d["verdict"]["rules"]["total"] == 15 and any(MSG in f for f in d["verdict"]["rules"]["failures"])


def test_rising_market_or_filter_off_changes_nothing(client, market, monkeypatch):  # noqa: F811
    monkeypatch.setattr(market_data, "_nifty_closes", lambda: RISING)
    on = _profile(client, min_nifty_vs_ema50_pct=2.0)
    assert _run(client, on)["passed_size"] == 1                                   # GOODCO still passes
    assert client.post(f"/api/v1/stocks/GOODCO/analyze?profile_id={on}").json()["verdict"]["rules"]["total"] == 15
    monkeypatch.setattr(market_data, "_nifty_closes", lambda: FALLING)
    off = _profile(client)                                                        # 0 = off: not evaluated at all
    assert _run(client, off)["passed_size"] == 1
    assert client.post(f"/api/v1/stocks/GOODCO/analyze?profile_id={off}").json()["verdict"]["rules"]["total"] == 14


def test_unavailable_nifty_skips_the_filter(client, market, monkeypatch):  # noqa: F811
    monkeypatch.setattr(market_data, "_nifty_closes", lambda: None)
    pid = _profile(client, min_nifty_vs_ema50_pct=2.0)
    d = client.post(f"/api/v1/stocks/GOODCO/analyze?profile_id={pid}").json()
    assert d["filters"]["passed"] is True and "Nifty 50 trend unavailable, filter skipped" in d["filters"]["failures"]


# --- backtests: evaluated per scan date ---------------------------------------------------------------------

def test_backtest_makes_no_picks_while_nifty_is_below_its_ema(world, monkeypatch):  # noqa: F811
    from app.db.session import SessionLocal
    from app.engine.params import ScreenParams
    from app.models import BacktestTrade, Profile

    idx = pd.bdate_range(end=END, periods=420)
    level = np.full(len(idx), 20000.0)
    dip = (idx >= pd.Timestamp("2026-04-06")) & (idx <= pd.Timestamp("2026-05-08"))
    level[dip] = 17000.0                                                          # 15% below for five weeks
    series = pd.Series(level, index=idx)
    monkeypatch.setattr(market_data, "nifty_closes_range", lambda start, end: series)

    def scan_dates(bt_id):
        with SessionLocal() as db:
            return {t.scan_date for t in db.query(BacktestTrade).filter_by(backtest_id=bt_id)}

    with SessionLocal() as db:
        base = backtest_service.create(db, world["pid"], "2026-03-02", END).id
        p = Profile(name="BT filter", owner="T", params_json=ScreenParams.from_dict(
            {**OPEN_PARAMS, "min_nifty_vs_ema50_pct": 2.0}).to_json())
        db.add(p)
        db.commit()
        filtered = backtest_service.create(db, p.id, "2026-03-02", END).id
    in_dip = lambda dates: {d for d in dates if "2026-04-06" <= d <= "2026-05-08"}  # noqa: E731
    assert in_dip(scan_dates(base))                                               # without the filter it trades there
    assert not in_dip(scan_dates(filtered))                                       # with it: no new picks in the dip
    assert scan_dates(filtered) - in_dip(scan_dates(base))                        # but it trades outside the dip
