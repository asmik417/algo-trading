"""Backtest endpoints: 202 start, the exact 409 body while one is active, list order and filter, poll, results only
when done, delete rules, 404/400/401. Synthetic market and inline execution (see test_backtest_service.world).
"""
from app.services import backtest_service
from tests.test_backtest_service import END, world  # noqa: F401  (fixture)

API = "/api/v1/backtests"


def _start(client, pid, expect=202, **kw):
    r = client.post(API, json={"profile_id": pid, "start_date": "2026-03-02", "end_date": END, **kw})
    assert r.status_code == expect, r.text
    return r.json()


def test_start_poll_results_list_delete(client, world):  # noqa: F811
    pid = world["pid"]
    bt = _start(client, pid)
    assert (bt["status"], bt["frequency"], bt["entry_rule"], bt["fundamentals_mode"], bt["cost_pct"]) == \
        ("queued", "weekly", "next_close", "point_in_time", 0.3)      # the defaults
    assert bt["profile_name"] == "BT" and bt["capital_per_trade"] == 10_000.0 and bt["caveats"]

    done = client.get(f"{API}/{bt['id']}").json()
    assert done["status"] == "done" and done["summary"]["trades"] > 0 and done["progress"]["phase"] == "done"
    res = client.get(f"{API}/{bt['id']}/results").json()
    assert res["backtest"]["id"] == bt["id"] and len(res["trades"]) == done["summary"]["trades"]
    assert res["equity_curve"] == sorted(res["equity_curve"], key=lambda p: p["date"])

    other = _start(client, pid, entry_rule="optimal_limit", cost_pct=0.0, capital_per_trade=5000)
    assert [b["id"] for b in client.get(API).json()] == [other["id"], bt["id"]]          # newest first
    assert client.get(f"{API}?profile_id={pid}&limit=1").json()[0]["id"] == other["id"]
    assert client.get(f"{API}?profile_id=999").json() == []
    assert client.get(f"{API}/{other['id']}").json()["capital_per_trade"] == 5000.0

    assert client.delete(f"{API}/{bt['id']}").status_code == 204
    assert client.get(f"{API}/{bt['id']}").status_code == 404
    assert client.get(f"{API}/{bt['id']}/results").status_code == 404
    assert client.delete(f"{API}/{bt['id']}").status_code == 404


def test_only_one_at_a_time_and_states(client, world, monkeypatch):  # noqa: F811
    monkeypatch.setattr(backtest_service, "_spawn", lambda bt_id: None)                   # stays queued
    pid = world["pid"]
    first = _start(client, pid)
    r = client.post(API, json={"profile_id": pid, "start_date": "2026-03-02", "end_date": END})
    assert r.status_code == 409 and r.json() == {"detail": "A backtest is already running", "backtest_id": first["id"]}
    assert client.get(f"{API}/{first['id']}/results").status_code == 409                  # not done yet
    assert client.delete(f"{API}/{first['id']}").status_code == 409                       # not while queued
    backtest_service.execute(first["id"])
    assert client.get(f"{API}/{first['id']}/results").status_code == 200
    assert _start(client, pid)["status"] == "queued"                                       # the slot is free again


def test_validation_and_auth(client, anon_client, world):  # noqa: F811
    pid = world["pid"]
    _start(client, pid, expect=400, frequency="monthly")
    _start(client, pid, expect=400, entry_rule="market_open")
    _start(client, pid, expect=400, fundamentals_mode="magic")
    _start(client, pid, expect=400, cost_pct=6)
    _start(client, pid, expect=400, end_date="2026-02-01")                                  # before start
    assert client.post(API, json={"profile_id": pid}).status_code == 400                   # dates missing
    _start(client, 999, expect=404)
    anon_client.cookies.clear()
    assert anon_client.get(API).status_code == 401
