"""Watchlist runs: requested order kept, duplicates collapsed, unknown/failed symbols reported (not fatal),
filter failures included, never shown in the Suggested tab, trackable like run picks. Synthetic market, no network.
"""
from app.services import run_registry, suggestion_service
from tests.test_suggestion_runs import _profile, _run, market  # noqa: F401  (fixture)


def _watch(client, pid, symbols, expect=202):
    r = client.post(f"/api/v1/profiles/{pid}/watchlist-runs", json={"symbols": symbols})
    assert r.status_code == expect, r.text
    return r.json()


def _inline(monkeypatch):
    monkeypatch.setattr(suggestion_service, "_spawn_watchlist", suggestion_service.execute_watchlist_run)


def test_order_duplicates_unknown_and_failures(client, market, monkeypatch):  # noqa: F811
    _inline(monkeypatch)
    pid = _profile(client)
    started = _watch(client, pid, ["priceyco", "GOODCO", "NOPE", " goodco ", "", "ETFCO", "DELISTED"])
    assert started["kind"] == "watchlist" and started["symbols"] == ["PRICEYCO", "GOODCO", "NOPE", "ETFCO", "DELISTED"]

    body = client.get(f"/api/v1/runs/{started['id']}/results").json()
    run = body["run"]
    assert (run["status"], run["kind"], run["universe_size"], run["scored_size"], run["passed_size"]) == \
        ("done", "watchlist", 5, 3, 1)
    assert run["progress"] == {"phase": "done", "done": 5, "total": 5, "current_symbol": None}  # one tick per symbol
    items = body["items"]
    assert [i["symbol"] for i in items] == ["PRICEYCO", "GOODCO", "NOPE", "ETFCO", "DELISTED"]  # requested order

    pricey, good, nope, etf, delisted = items
    assert pricey["filters"] == {"passed": False, "failures": ["P/E 95 above max 50"]} and pricey["error"] is None
    assert isinstance(pricey["id"], int) and pricey["source"] == "watchlist" and pricey["score"] is not None
    assert good["filters"]["passed"] is True and good["rank"] is None and good["stop_loss"] < good["price"]
    assert etf["filters"]["failures"][0] == suggestion_service.NO_FUNDAMENTALS  # analysed, failed, still listed
    for unknown in (nope, delisted):  # WatchlistMiss: exactly these fields, every one null except symbol/error
        assert unknown == {"id": None, "symbol": unknown["symbol"], "error":
                           f"{unknown['symbol']} is not in the NSE universe for 2026-11-04.", "filters": None,
                           "score": None, "signal": None, "stage": None, "price": None, "is_tracked": False,
                           "position_id": None}
    assert pricey["error"] is None and set(pricey) >= {"filters", "error", "entry_optimal", "market_cap_bucket"}  # Hit


def test_watchlist_never_in_suggested_tab_or_full_run_list(client, market, monkeypatch):  # noqa: F811
    _inline(monkeypatch)
    pid = _profile(client)
    full = _run(client, pid)
    wl = _watch(client, pid, ["GOODCO", "PRICEYCO"])  # finishes after the full run: newest done run
    suggested = client.get(f"/api/v1/profiles/{pid}/suggestions").json()
    assert suggested["run"]["id"] == full["id"] and suggested["run"]["kind"] == "full"
    assert {i["source"] for i in suggested["items"]} == {"run"} and [i["symbol"] for i in suggested["items"]] == ["GOODCO"]
    assert client.get(f"/api/v1/profiles/{pid}/suggestions?run_id={wl['id']}").json()["items"] == []
    assert [r["id"] for r in client.get(f"/api/v1/profiles/{pid}/runs").json()] == [full["id"]]
    assert [r["id"] for r in client.get(f"/api/v1/profiles/{pid}/watchlist-runs").json()] == [wl["id"]]
    assert client.get(f"/api/v1/runs/{full['id']}").json()["symbols"] is None


def test_tracking_works_like_run_items(client, market, monkeypatch):  # noqa: F811
    _inline(monkeypatch)
    pid = _profile(client)
    wl = _watch(client, pid, ["GOODCO", "PRICEYCO"])
    good = client.get(f"/api/v1/runs/{wl['id']}/results").json()["items"][0]
    assert good["is_tracked"] is False and good["position_id"] is None
    pos = client.post("/api/v1/positions", json={"profile_id": pid, "suggestion_id": good["id"]}).json()
    assert (pos["suggestion_id"], pos["stage"], pos["signal"]) == (good["id"], good["stage"], good["signal"])
    again = client.get(f"/api/v1/runs/{wl['id']}/results").json()["items"]
    assert (again[0]["is_tracked"], again[0]["position_id"]) == (True, pos["id"])
    assert again[1]["is_tracked"] is False
    detail = client.get(f"/api/v1/suggestions/{good['id']}").json()  # the dialog opens for watchlist items too
    assert detail["source"] == "watchlist" and detail["plan"]["disclaimer"]


def test_one_symbol_crashing_does_not_fail_the_run(client, market, monkeypatch):  # noqa: F811
    _inline(monkeypatch)
    real = suggestion_service.load_fundamentals

    def flaky(day, sym, force=False):
        if sym == "PRICEYCO":
            raise ConnectionError("yfinance down")
        return real(day, sym, force)

    monkeypatch.setattr(suggestion_service, "load_fundamentals", flaky)
    pid = _profile(client)
    body = client.get(f"/api/v1/runs/{_watch(client, pid, ['PRICEYCO', 'GOODCO'])['id']}/results").json()
    assert body["run"]["status"] == "done"
    assert body["items"][0]["error"] == "Could not analyse PRICEYCO: ConnectionError" and body["items"][1]["error"] is None


def test_validation_and_errors(client, market, monkeypatch):  # noqa: F811
    monkeypatch.setattr(suggestion_service, "_spawn_watchlist", lambda run_id: None)
    pid = _profile(client)
    _watch(client, pid, [], expect=400)
    _watch(client, pid, ["  ", ""], expect=400)
    _watch(client, pid, [f"S{i}" for i in range(51)], expect=400)
    _watch(client, pid, [f"S{i % 50}" for i in range(80)])  # 80 entries but 50 distinct: allowed
    _watch(client, pid, ["X" * 31], expect=400)
    assert client.post(f"/api/v1/profiles/{pid}/watchlist-runs", json={}).status_code == 400
    assert client.post("/api/v1/profiles/999/watchlist-runs", json={"symbols": ["TCS"]}).status_code == 404
    assert client.get("/api/v1/runs/999/results").status_code == 404


def test_not_blocked_by_an_active_full_run(client, market, monkeypatch):  # noqa: F811
    monkeypatch.setattr(suggestion_service, "_spawn", lambda run_id, force: None)  # full run stays queued
    pid = _profile(client)
    full = client.post(f"/api/v1/profiles/{pid}/runs").json()
    _inline(monkeypatch)
    wl = _watch(client, pid, ["GOODCO"])
    assert wl["id"] != full["id"] and client.get(f"/api/v1/runs/{wl['id']}").json()["status"] == "done"
    assert run_registry.active_run(pid) == full["id"]  # the full run still holds its slot
    assert client.get(f"/api/v1/runs/{full['id']}/results").status_code == 400  # results are for watchlist runs
