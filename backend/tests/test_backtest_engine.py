"""Backtest engine (app/engine/backtest), unit by unit on small synthetic histories, plus the no-look-ahead proof:
changing or adding bars after a scan date never changes that scan's picks or plans. No DB, no network.
"""
from datetime import date

import numpy as np
import pandas as pd
import pytest

from app.engine.backtest import calendar, fundamentals, history, patterns, replay, simulate, stats
from app.engine.backtest.replay import Pick
from app.engine.backtest.simulate import NO_FILL, CORPORATE_ACTION, Trade


def bars(closes, start="2026-01-05", low=None, turnover=500.0):
    idx = pd.bdate_range(start, periods=len(closes))
    c = np.asarray(closes, dtype=float)
    lows = np.asarray(low, dtype=float) if low is not None else c * 0.99
    return pd.DataFrame({"Open": c, "High": c * 1.01, "Low": lows, "Close": c, "Volume": 1000.0,
                         "TurnoverLacs": turnover}, index=idx)


def pick(symbol="AAA", scan="2026-01-05", stop=90.0, target=120.0, exit_date="2026-01-30", optimal=99.0, **kw):
    return Pick(symbol=symbol, scan_date=pd.Timestamp(scan), rank=kw.get("rank", 1), score=70.0,
                signal="🔵 Breakout Confirmed", stage="Breakout", market_cap_bucket="Mid Cap", sector="Tech",
                entry_optimal=optimal, stop_loss=stop, target=target, planned_exit_date=exit_date,
                avg_turnover_lacs=kw.get("turnover", 500.0))


# --- calendar --------------------------------------------------------------------------------------

def test_weekly_scan_dates_are_last_trading_day_of_each_iso_week():
    days = list(pd.bdate_range("2025-01-01", "2026-03-31"))
    days = [d for d in days if d != pd.Timestamp("2026-03-06")]  # a Friday holiday: Thursday ends that week
    start, scans = calendar.scan_dates(days, date(2026, 2, 23), date(2026, 3, 13), "weekly", min_history=10)
    assert start == date(2026, 2, 23)
    assert [d.date().isoformat() for d in scans] == ["2026-02-27", "2026-03-05", "2026-03-13"]


def test_daily_and_clamping():
    days = list(pd.bdate_range("2026-01-01", periods=300))
    start, scans = calendar.scan_dates(days, date(2025, 1, 1), days[-1].date(), "daily")
    assert start == days[250].date() and scans[0] == days[250] and len(scans) == 50  # 250 days precede the first
    assert calendar.scan_dates(days[:250], date(2025, 1, 1), date(2027, 1, 1)) == (None, [])
    with pytest.raises(ValueError):
        calendar.scan_dates(days, date(2026, 1, 1), date(2027, 1, 1), "monthly")


# --- history -----------------------------------------------------------------------------------------

def test_upto_and_after():
    h = bars(range(100, 110))
    assert history.upto(h, "2026-01-09").index[-1] == pd.Timestamp("2026-01-09")
    assert list(history.after(h, "2026-01-09", "2026-01-13").index.day) == [12, 13]
    cut = history.upto_all({"A": h, "LATE": bars([5, 6], start="2026-02-02")}, "2026-01-09")
    assert set(cut) == {"A"}  # no bars yet -> not in the universe that day
    assert history.avg_turnover_lacs(bars([1] * 19)) is None and history.avg_turnover_lacs(bars([1] * 25)) == 500.0


# --- fundamentals ------------------------------------------------------------------------------------

BUNDLE = {
    "info": {"marketCap": 1e11, "returnOnEquity": 0.2, "earningsQuarterlyGrowth": 0.5, "trailingPE": 99.0,
             "sector": "Tech"},
    "quarterly": [{"period": p, "revenue": 100, "net_income": 10, "eps": e} for p, e in
                  [("2025-03-31", 2.0), ("2025-06-30", 2.5), ("2025-09-30", 3.0), ("2025-12-31", 3.5),
                   ("2026-03-31", 4.0)]],
    "cashflow": [{"period": "2025-03-31", "fcf": 1, "ocf": 2}, {"period": "2026-03-31", "fcf": 1, "ocf": 2}],
    "ok": True,
}


def test_point_in_time_drops_unpublished_rows_and_recomputes():
    h = bars([100.0] * 300, start="2025-01-01")
    out = fundamentals.point_in_time_bundle(BUNDLE, pd.Timestamp("2026-02-10"), 110.0, 220.0, h)
    # cutoff = scan - 45 days = 2025-12-27: the Dec-2025 quarter (ends 2025-12-31) is not yet published
    assert [r["period"] for r in out["quarterly"]] == ["2025-03-31", "2025-06-30", "2025-09-30"]
    assert [r["period"] for r in out["cashflow"]] == ["2025-03-31"]
    assert out["info"]["trailingPE"] is None              # only 3 published quarters
    assert out["info"]["marketCap"] == pytest.approx(5e10)  # scaled by 110 / 220
    assert "earningsQuarterlyGrowth" not in out["info"]     # today's latest-quarter growth is future data
    assert out["info"]["returnOnEquity"] == 0.2 and out["info"]["fiftyTwoWeekHigh"] == pytest.approx(101.0)
    assert BUNDLE["info"]["trailingPE"] == 99.0             # input not mutated
    later = fundamentals.point_in_time_bundle(BUNDLE, pd.Timestamp("2026-03-01"), 110.0, 220.0, h)
    assert later["info"]["trailingPE"] == pytest.approx(110 / (2.0 + 2.5 + 3.0 + 3.5))


def test_technical_only():
    w = {"earnings_acceleration": 25, "fundamental_quality": 20, "early_price_position": 10,
         "volume_accumulation": 15, "technical_setup": 20, "valuation": 10}
    out = fundamentals.technical_only_weights(w)
    assert out["earnings_acceleration"] == out["fundamental_quality"] == out["valuation"] == 0
    assert sum(out.values()) == pytest.approx(100) and out["technical_setup"] == pytest.approx(20 * 100 / 45)
    assert fundamentals.technical_only_bundle() == {"info": {}, "quarterly": [], "cashflow": [], "ok": True}


# --- simulation ----------------------------------------------------------------------------------------

def test_next_close_entry_stop_costs_r_and_excursions():
    h = bars([100, 101, 104, 95, 89, 120])        # scan on day 0 (Jan 5); entry Jan 6 close 101
    t = simulate.simulate_pick(pick(stop=90.0, target=130.0), h, "2026-02-27", "next_close", 0.3, 10_000)
    assert (t.entry_date, t.entry_price, t.qty, t.invested) == ("2026-01-06", 101.0, 99, 9999.0)
    assert (t.exit_reason, t.exit_date, t.exit_price, t.days_held) == ("stop_hit", "2026-01-09", 89.0, 3)
    assert t.pnl == pytest.approx(99 * (89 - 101) - 9999 * 0.003, abs=0.01)
    assert t.pnl_pct == pytest.approx(t.pnl / 9999 * 100, abs=0.01)
    assert t.r_multiple == pytest.approx((89 - 101) / (101 - 90), abs=0.01)
    assert (t.mfe_pct, t.mae_pct) == (pytest.approx(2.97, abs=0.01), pytest.approx(-11.88, abs=0.01))


def test_exit_order_stop_then_target_then_horizon():
    h = bars([100, 100, 105, 110])
    hz = simulate.simulate_pick(pick(stop=50, target=200, exit_date="2026-01-08"), h, "2026-02-27", "next_close", 0, 1e4)
    assert (hz.exit_reason, hz.exit_date) == ("horizon_closed", "2026-01-08")
    tg = simulate.simulate_pick(pick(stop=50, target=105, exit_date="2026-01-07"), h, "2026-02-27", "next_close", 0, 1e4)
    assert tg.exit_reason == "target_hit"  # target beats horizon on the same day
    both = bars([100, 100, 80])
    st = simulate.simulate_pick(pick(stop=90, target=200, exit_date="2026-01-07"), both, "2026-02-27", "next_close", 0, 1e4)
    assert st.exit_reason == "stop_hit"    # stop beats horizon on the same day


def test_open_at_end_is_marked_and_not_closed():
    h = bars([100, 100, 103, 104, 150])
    t = simulate.simulate_pick(pick(stop=50, target=200), h, "2026-01-08", "next_close", 0, 1e4)
    assert (t.exit_reason, t.exit_date, t.exit_price, t.days_held) == ("open", None, None, 2)  # Jan 9 bar is past end
    assert t.pnl == pytest.approx(100 * (104 - 100)) and not t.closed


def test_optimal_limit_fill_and_no_fill():
    lows = [100, 100, 99.5, 98.5, 100, 100, 100, 100]
    h = bars([100] * 8, low=lows)
    t = simulate.simulate_pick(pick(optimal=99.0), h, "2026-02-27", "optimal_limit", 0, 1e4)
    assert (t.entry_date, t.entry_price) == ("2026-01-08", 99.0)            # first session with Low <= 99
    late = bars([100] * 8, low=[100] * 6 + [90, 90])                        # only the 6th/7th session would fill
    assert simulate.simulate_pick(pick(optimal=99.0), late, "2026-02-27", "optimal_limit", 0, 1e4) == NO_FILL
    assert simulate.simulate_pick(pick(), bars([100, 100]), "2026-02-27", "next_close", 0, 50) == NO_FILL  # qty 0
    assert simulate.simulate_pick(pick(), bars([100]), "2026-02-27", "next_close", 0, 1e4) == NO_FILL     # no next bar


def test_corporate_action_while_held_drops_the_trade():
    h = bars([100, 100, 101, 40, 41])  # 1:2.5 split after entry
    assert simulate.simulate_pick(pick(stop=90), h, "2026-02-27", "next_close", 0, 1e4) == CORPORATE_ACTION


def test_nifty_change():
    n = pd.Series([100.0, 102.0, 97.0], index=pd.to_datetime(["2026-01-06", "2026-01-08", "2026-01-12"]))
    assert simulate.nifty_change_pct(n, "2026-01-07", "2026-01-12") == -3.0  # on/before each date
    assert simulate.nifty_change_pct(None, "2026-01-07", "2026-01-12") is None


def test_one_open_trade_per_symbol():
    h = {"AAA": bars([100] * 4 + [130] + [100] * 10), "BBB": bars([100] * 15)}
    picks = [pick("AAA", "2026-01-05", target=125), pick("AAA", "2026-01-07", target=125),   # first still open
             pick("AAA", "2026-01-09", target=125),                                           # exits Jan 9: free
             pick("BBB", "2026-01-07", stop=50, target=500, exit_date="2026-01-30")]
    res = simulate.simulate_all(picks, h, "2026-01-23", "next_close", 0, 1e4)
    assert [(t.symbol, t.scan_date) for t in res.trades] == [("AAA", "2026-01-05"), ("BBB", "2026-01-07"),
                                                             ("AAA", "2026-01-09")]
    assert res.trades[0].exit_date == "2026-01-09" and res.skipped_repeat == 1


# --- loss patterns -----------------------------------------------------------------------------------------

def _trade(**kw) -> Trade:
    base = dict(symbol="AAA", scan_date="2026-01-05", entry_date="2026-01-06", entry_price=100.0, qty=100,
                invested=10_000.0, stop_loss=90.0, target=120.0, planned_exit_date="2026-01-30", signal="s", stage="t",
                score=70.0, market_cap_bucket="Mid Cap", sector="Tech", exit_date="2026-01-08", exit_price=89.0,
                exit_reason="stop_hit", pnl=-1100.0, pnl_pct=-11.0, r_multiple=-1.1, days_held=2, mfe_pct=0.0,
                mae_pct=-11.0, nifty_pct=0.0, avg_turnover_lacs=500.0)
    base.update(kw)
    return Trade(**base)


def test_loss_tags():
    flat = bars([100] * 40, start="2025-12-01")
    recovered = bars([100] * 25 + [89, 105] + [100] * 13, start="2025-12-01")  # back above entry after the stop
    t = _trade(entry_date="2026-01-02", exit_date="2026-01-05")
    assert "stop_too_tight" in patterns.tag_loss(t, recovered)
    assert "stop_too_tight" not in patterns.tag_loss(t, flat)                       # never got back above entry
    assert "stop_too_tight" not in patterns.tag_loss(_trade(entry_date="2026-01-02", exit_date="2026-01-05",
                                                            days_held=6), recovered)  # not within 5 sessions
    ext = bars([100] * 30 + [112], start="2025-12-01")
    assert "bought_extended" in patterns.tag_loss(_trade(entry_date="2026-01-12", entry_price=112.0), ext)
    assert "whole_market_fell" in patterns.tag_loss(_trade(nifty_pct=-3.0), flat)
    held = _trade(exit_reason="horizon_closed", mfe_pct=10.0, pnl=-50.0)   # target 20% away, was up 10%
    assert "held_too_long" in patterns.tag_loss(held, flat)
    dip = bars([100] * 26 + [94, 100, 100] + [100] * 11, start="2025-12-01")  # -6 in the first 3 sessions, risk 10
    assert "bad_entry_timing" in patterns.tag_loss(_trade(entry_date="2026-01-05"), dip)
    assert "low_liquidity" in patterns.tag_loss(_trade(avg_turnover_lacs=50.0), flat)
    assert patterns.tag_loss(_trade(exit_reason="horizon_closed", mfe_pct=1.0), flat) == ["other"]


def test_tag_losses_only_tags_closed_losers():
    flat = bars([100] * 40, start="2025-12-01")
    trades = [_trade(), _trade(pnl=500.0, exit_reason="target_hit"), _trade(exit_reason="open", exit_date=None)]
    patterns.tag_losses(trades, {"AAA": flat})
    assert trades[0].tags and trades[1].tags == [] and trades[2].tags == []


# --- summary maths ----------------------------------------------------------------------------------------------

def test_summary_breakdowns_curve_drawdown_and_patterns():
    trades = [
        _trade(pnl=1000.0, pnl_pct=10.0, r_multiple=1.0, exit_reason="target_hit", exit_date="2026-01-10",
               days_held=4, nifty_pct=1.0, entry_date="2026-01-06", signal="A"),
        _trade(pnl=-500.0, pnl_pct=-5.0, r_multiple=-0.5, exit_date="2026-01-12", days_held=2, nifty_pct=-1.0,
               entry_date="2026-01-07", signal="A", tags=["stop_too_tight", "other"]),
        _trade(pnl=-800.0, pnl_pct=-8.0, r_multiple=-0.8, exit_date="2026-02-03", days_held=6, nifty_pct=None,
               entry_date="2026-02-01", signal="B", sector=None, tags=["stop_too_tight"]),
        _trade(pnl=300.0, pnl_pct=3.0, r_multiple=0.3, exit_reason="open", exit_date=None, entry_date="2026-02-02",
               signal="B"),
    ]
    s = stats.summary(trades, skipped_repeat=2, skipped_no_fill=1, capital_per_trade=10_000)
    assert (s["trades"], s["closed"], s["wins"], s["losses"], s["open_at_end"]) == (4, 3, 1, 2, 1)
    assert s["win_rate_pct"] == pytest.approx(33.33) and s["profit_factor"] == pytest.approx(1000 / 1300, abs=0.01)
    assert s["expectancy_r"] == pytest.approx((1.0 - 0.5 - 0.8) / 3, abs=0.01)
    assert (s["avg_win_pct"], s["avg_loss_pct"], s["total_pnl"]) == (10.0, -6.5, 0.0)  # open trade counts in total
    assert s["avg_days_held"] == 4.0 and s["nifty_avg_pct"] == 0.0
    assert s["exits"] == {"target_hit": 1, "stop_hit": 2, "horizon_closed": 0, "open": 1}
    assert (s["skipped_repeat"], s["skipped_no_fill"]) == (2, 1)

    curve = stats.equity_curve(trades)
    assert curve == [{"date": "2026-01-10", "pnl": 1000.0}, {"date": "2026-01-12", "pnl": 500.0},
                     {"date": "2026-02-03", "pnl": -300.0}]
    assert stats.max_drawdown_pct(curve, 10_000) == pytest.approx(1300 / 100_000 * 100)  # peak 1000 -> -300
    assert stats.summary([trades[0]], 0, 0, 10_000)["profit_factor"] is None              # no losses

    b = stats.breakdowns(trades)
    assert b["by_signal"][0] == {"key": "A", "trades": 2, "win_rate_pct": 50.0, "avg_pnl_pct": 2.5, "total_pnl": 500.0}
    assert [r["key"] for r in b["by_month"]] == ["2026-01", "2026-02"] and b["by_sector"][-1]["key"] == "Unknown"
    lp = stats.loss_patterns(trades, {"stop_too_tight": "Stop-loss was too tight", "other": "Other"})
    assert lp == [{"key": "stop_too_tight", "label": "Stop-loss was too tight", "count": 2, "share_pct": 100.0},
                  {"key": "other", "label": "Other", "count": 1, "share_pct": 50.0}]


# --- replay and the no-look-ahead proof ----------------------------------------------------------------------------

STRONG = {"info": {"trailingPE": 20.0, "returnOnEquity": 0.25, "operatingMargins": 0.2, "profitMargins": 0.12,
                   "debtToEquity": 20.0, "marketCap": 3e11, "sector": "Tech"},
          "quarterly": [{"period": f"Q{i}", "revenue": r, "net_income": n, "eps": n / 10}
                        for i, (r, n) in enumerate(zip([100, 105, 112, 120, 130], [10, 11, 13, 12, 30]))],
          "cashflow": [{"period": "FY", "fcf": 5e9, "ocf": 6e9}], "ok": True}


def _market(seed=11, n=320, end="2026-06-30"):
    rng = np.random.default_rng(seed)
    out = {}
    for k in range(12):
        base = 200 + 50 * k
        closes = base * np.cumprod(1 + rng.normal(0.0015, 0.015, n))
        vol = rng.integers(200_000, 900_000, n).astype(float)
        idx = pd.bdate_range(end=end, periods=n)
        out[f"S{k:02d}"] = pd.DataFrame({"Open": closes, "High": closes * 1.01, "Low": closes * 0.99, "Close": closes,
                                         "Volume": vol, "DelivPct": 50.0, "TurnoverLacs": closes * vol / 1e5}, index=idx)
    return out


def _scan(histories, scan_date):
    from app.engine.params import ScreenParams
    from app.services import plan_service, suggestion_service

    suggestion_service._stage1_cache.clear()  # never let a cached stage-1 result hide a look-ahead
    params = ScreenParams.from_dict({"min_score": 0.0, "rsi_min": 0.0, "rsi_max": 100.0, "max_3m_runup_pct": 500.0,
                                     "min_volume_ratio": 0.0, "max_dist_from_52w_high_pct": 0.0,
                                     "require_above_200ema": False, "min_price": 1.0, "min_avg_turnover_lacs": 0.0,
                                     "shortlist_size": 4})  # < 12 stocks, so the prefilter's ranking matters too
    symbols = replay.shortlist(scan_date, histories, params, suggestion_service.prefilter)
    return replay.picks(scan_date, histories, symbols, params, score=suggestion_service.score_symbol,
                        plan=plan_service.build_plan, bundle_for=lambda s, d, h: STRONG, max_suggestions=10)


def test_changing_bars_after_the_scan_date_never_changes_picks_or_plans():
    base = _market()
    scan = base["S00"].index[-60]
    before = _scan(base, scan)
    assert before, "the synthetic market should produce picks"

    rng = np.random.default_rng(99)
    altered = {}
    for sym, h in base.items():
        h = h.copy()
        future = h.index > scan
        shock = rng.uniform(0.2, 5.0, future.sum())       # wild changes after the scan date
        for col in ("Open", "High", "Low", "Close"):
            h.loc[future, col] = h.loc[future, col] * shock
        h.loc[future, "Volume"] *= 50
        extra = h.tail(1).copy()
        extra.index = [h.index[-1] + pd.offsets.BDay(30)]  # and new bars far in the future
        altered[sym] = pd.concat([h, extra])
    altered["NEWCO"] = _market(seed=5)["S03"].loc[lambda d: d.index > scan]  # a stock that only lists later
    after = _scan(altered, scan)
    assert after == before  # same symbols, ranks, scores, signals, stages and every plan number
    assert len(before) < 12  # the shortlist really cut the universe
