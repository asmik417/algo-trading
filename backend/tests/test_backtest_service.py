"""Backtest service: a full run on a synthetic market (both fundamentals modes), persistence, results assembly,
one-at-a-time rule, delete/results states, validation, failure and restart recovery. No network.
"""
import pytest

from app.db.session import SessionLocal
from app.engine.params import ScreenParams
from app.models import Backtest, BacktestTrade, Profile
from app.services import backtest_service, market_data, suggestion_service
from app.services.errors import BadInput, Conflict, NotFound
from tests.test_backtest_engine import _market

END = "2026-06-30"
OPEN_PARAMS = {"min_score": 0.0, "rsi_min": 0.0, "rsi_max": 100.0, "max_3m_runup_pct": 500.0, "min_volume_ratio": 0.0,
               "max_dist_from_52w_high_pct": 0.0, "require_above_200ema": False, "min_price": 1.0,
               "min_avg_turnover_lacs": 0.0, "max_pe": 0.0, "min_roe_pct": -50.0, "min_profit_growth_pct": -100.0,
               "max_debt_to_equity": 0.0, "allowed_caps": ["Large Cap", "Mid Cap", "Small Cap"], "max_suggestions": 3}
QUARTERS = ["2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31", "2026-03-31", "2026-06-30"]
BUNDLE = {"info": {"returnOnEquity": 0.25, "operatingMargins": 0.2, "profitMargins": 0.12, "debtToEquity": 20.0,
                   "marketCap": 3e11, "sector": "Tech", "earningsQuarterlyGrowth": 9.9},
          "quarterly": [{"period": p, "revenue": 100 + 5 * i, "net_income": 10 + i, "eps": 1.0 + i / 10}
                        for i, p in enumerate(QUARTERS)],
          "cashflow": [{"period": "2025-03-31", "fcf": 5e9, "ocf": 6e9}], "ok": True}


@pytest.fixture()
def world(clean_db, monkeypatch):
    market = _market(n=420, end=END)
    fetched: list[str] = []
    monkeypatch.setattr(market_data, "histories_for_range", lambda start, end, progress=None: market)
    monkeypatch.setattr(market_data, "panel_day", lambda: END)
    monkeypatch.setattr(market_data, "latest_close", lambda sym: float(market[sym]["Close"].iloc[-1]))
    monkeypatch.setattr(suggestion_service, "load_fundamentals",
                        lambda day, sym, force=False: fetched.append(sym) or BUNDLE)
    monkeypatch.setattr(backtest_service, "_spawn", backtest_service.execute)  # run inline
    with SessionLocal() as db:
        p = Profile(name="BT", owner="T", params_json=ScreenParams.from_dict(OPEN_PARAMS).to_json(), is_active=True)
        db.add(p)
        db.commit()
        pid = p.id
    return {"pid": pid, "market": market, "fetched": fetched}


def _create(pid, **kw):
    with SessionLocal() as db:
        args = {"start_date": "2026-03-02", "end_date": END, **kw}
        bt = backtest_service.create(db, pid, **args)
        return bt.id


def _load(bt_id):
    with SessionLocal() as db:
        bt = db.get(Backtest, bt_id)
        return backtest_service.to_schema(bt), (backtest_service.results(db, bt_id) if bt.status == "done" else None)


def test_point_in_time_run_end_to_end(world):
    bt_id = _create(world["pid"])
    bt, res = _load(bt_id)
    assert bt["status"] == "done", bt["error"]
    assert bt["progress"] == {"phase": "done", "done": bt["scan_count"], "total": bt["scan_count"], "current_symbol": None}
    assert bt["scan_count"] == 18 and bt["start_date"] == "2026-03-02"     # weekly scans Mar-Jun 2026
    assert bt["capital_per_trade"] == 10_000.0 and bt["params"]["max_suggestions"] == 3
    assert any("today's values" in c for c in bt["caveats"])
    s = bt["summary"]
    assert s["trades"] == len(res["trades"]) > 0
    assert s["trades"] == s["closed"] + s["open_at_end"] and s["closed"] >= s["wins"] + s["losses"]
    assert s["exits"]["open"] == s["open_at_end"]
    assert set(res) == {"backtest", "by_signal", "by_stage", "by_market_cap", "by_sector", "by_month",
                        "loss_patterns", "equity_curve", "trades"}
    t = res["trades"][0]
    assert t["entry_date"] > t["scan_date"] and isinstance(t["tags"], list) and isinstance(t["id"], int)
    assert sum(r["trades"] for r in res["by_month"]) == s["trades"]
    assert all(t["tags"] for t in res["trades"] if t["exit_reason"] != "open" and t["pnl"] < 0)
    assert len(set(world["fetched"])) == len(world["fetched"])               # each bundle fetched once


def test_point_in_time_really_changes_fundamentals_by_scan_date(world, monkeypatch):
    seen = []
    real = suggestion_service.score_symbol
    monkeypatch.setattr(suggestion_service, "score_symbol",
                        lambda sym, h, bundle, params, **kw: seen.append((h.index[-1], bundle)) or real(sym, h, bundle, params, **kw))
    _create(world["pid"])
    early = next(b for d, b in seen if d < __import__("pandas").Timestamp("2026-04-01"))
    late = next(b for d, b in seen if d > __import__("pandas").Timestamp("2026-06-20"))
    assert len(early["quarterly"]) < len(late["quarterly"])                  # later scans see more published quarters
    assert "earningsQuarterlyGrowth" not in early["info"]                     # future data removed
    assert early["info"]["marketCap"] != BUNDLE["info"]["marketCap"]          # scaled by the scan-date close


def test_technical_only_run(world):
    bt_id = _create(world["pid"], fundamentals_mode="technical_only", entry_rule="optimal_limit", frequency="daily")
    bt, res = _load(bt_id)
    assert bt["status"] == "done", bt["error"]
    assert world["fetched"] == []                                            # no fundamentals fetched at all
    assert any("Technical-only" in c for c in bt["caveats"])
    assert bt["scan_count"] > 80 and bt["frequency"] == "daily"
    assert bt["summary"]["trades"] + bt["summary"]["skipped_no_fill"] + bt["summary"]["skipped_repeat"] > 0


def test_start_is_clamped_and_stored(world):
    bt, _ = _load(_create(world["pid"], start_date="2025-01-01"))
    assert bt["status"] == "done" and bt["start_date"] > "2025-01-01"         # 250 sessions must precede scan 1
    assert any("Start moved from 2025-01-01" in c for c in bt["caveats"])


def test_one_backtest_at_a_time_and_states(world, monkeypatch):
    monkeypatch.setattr(backtest_service, "_spawn", lambda bt_id: None)        # stays queued
    first = _create(world["pid"])
    with pytest.raises(Conflict) as err:
        _create(world["pid"])
    assert err.value.detail == "A backtest is already running" and err.value.extra == {"backtest_id": first}
    with SessionLocal() as db:
        with pytest.raises(Conflict):
            backtest_service.results(db, first)                               # not done
        with pytest.raises(Conflict):
            backtest_service.delete(db, first)                                # not while queued/running
    backtest_service.execute(first)
    with SessionLocal() as db:
        assert db.get(Backtest, first).status == "done" and db.query(BacktestTrade).count() > 0
        backtest_service.delete(db, first)
        assert db.get(Backtest, first) is None and db.query(BacktestTrade).count() == 0   # trades cascade
        with pytest.raises(NotFound):
            backtest_service.get(db, first)


@pytest.mark.parametrize("kw, message", [
    ({"start_date": END, "end_date": "2026-03-02"}, "before end_date"),
    ({"end_date": "2026-07-15"}, "last trading day"),
    ({"start_date": "2022-01-01"}, "at most 3 years"),
    ({"cost_pct": 5.5}, "cost_pct"),
    ({"cost_pct": -1}, "cost_pct"),
    ({"capital_per_trade": 0}, "positive"),
    ({"start_date": "01-03-2026"}, "date like"),
])
def test_validation(world, kw, message):
    with pytest.raises(BadInput) as err:
        _create(world["pid"], **kw)
    assert message in err.value.detail


def test_failure_is_recorded_and_restart_recovery(world, monkeypatch):
    def boom(start, end, progress=None):
        raise RuntimeError("bhavcopy archive down")
    monkeypatch.setattr(market_data, "histories_for_range", boom)
    bt, _ = _load(_create(world["pid"]))
    assert bt["status"] == "failed" and "bhavcopy archive down" in bt["error"] and bt["finished_at"]
    with SessionLocal() as db:  # a row left 'running' by a dead process
        db.add(Backtest(profile_id=world["pid"], status="running", start_date="2026-03-02", end_date=END,
                        capital_per_trade=1e4))
        db.commit()
        backtest_service.recover_interrupted(db)
        assert {b.status for b in db.query(Backtest)} == {"failed"}
        assert "restarted" in db.query(Backtest).order_by(Backtest.id.desc()).first().error
