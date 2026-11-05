"""Step 8: the paper tracker — open, daily marks, stop/target/due, extend/shorten/close/notes, stats, detail.
Prices come from a synthetic panel that the tests advance day by day; no network.
"""
import pandas as pd
import pytest

from app.db.session import SessionLocal
from app.models import Suggestion
from app.services import market_data, tracker_service

DAYS = pd.bdate_range("2026-07-01", "2026-11-20")  # history before, then the days the tests walk through
OPEN_DAY = "2026-11-04"


def _panel(prices: dict[str, dict[str, float]], upto: str) -> pd.DataFrame:
    """prices: symbol -> {iso day: close} overrides; every other day closes at 100."""
    rows = []
    for sym, overrides in prices.items():
        for d in DAYS[DAYS <= pd.Timestamp(upto)]:
            c = overrides.get(d.date().isoformat(), 100.0)
            rows.append({"symbol": sym, "date": d, "open": c, "high": c * 1.01, "low": c * 0.99, "close": c,
                         "volume": 1000, "turnover_lacs": 100.0, "deliv_qty": 500, "deliv_pct": 50.0})
    return pd.DataFrame(rows).sort_values(["symbol", "date"]).reset_index(drop=True)


@pytest.fixture()
def world(client, monkeypatch):
    """Returns helpers: set(day, prices) installs the panel up to `day`; suggest(...) inserts a suggestion."""
    monkeypatch.setattr(market_data, "_record_panel_day", lambda day: None)
    monkeypatch.setattr(market_data, "_nifty_closes", lambda: pd.Series([100.0, 103.0], index=pd.to_datetime([OPEN_DAY, "2026-11-20"])))
    state = {"prices": {s: {} for s in ("AAA", "BBB", "CCC", "DDD")}}

    def set_day(day, **prices):
        for sym, overrides in prices.items():
            state["prices"].setdefault(sym, {}).update(overrides)
        market_data.set_panel(_panel(state["prices"], day))

    def suggest(pid, symbol, stop=90.0, target=120.0, exit_date="2026-11-11"):
        with SessionLocal() as db:
            s = Suggestion(run_id=None, source="explore", profile_id=pid, symbol=symbol, trading_day=OPEN_DAY, rank=None,
                           score=75.0, stage="Breakout", signal="🔵 Breakout Confirmed", price=100.0,
                           entry_aggressive=100.0, entry_optimal=98.0, entry_conservative=95.0, stop_loss=stop,
                           target=target, risk_reward=2.0, horizon_days=5, planned_exit_date=exit_date,
                           timing_note="t", exit_note="e", payload_json='{"market_cap_bucket": "Mid Cap"}')
            db.add(s)
            db.commit()
            return s.id

    set_day(OPEN_DAY)
    pid = client.get("/api/v1/profiles/active").json()["id"]
    return {"set": set_day, "suggest": suggest, "pid": pid}


def _open(client, pid, sid=None, **body):
    return client.post("/api/v1/positions", json={"profile_id": pid, **({"suggestion_id": sid} if sid else {}), **body})


def _mark(as_of):
    with SessionLocal() as db:
        return tracker_service.mark_all(db, as_of)


def test_open_from_suggestion(client, world):
    pid, sid = world["pid"], world["suggest"](world["pid"], "AAA")
    world["set"](OPEN_DAY, AAA={OPEN_DAY: 123.0})
    r = _open(client, pid, sid)
    assert r.status_code == 201, r.text
    p = r.json()
    assert (p["symbol"], p["entry_price"], p["qty"], p["invested"], p["capital"], p["cash_left"]) == \
        ("AAA", 123.0, 81, 9963.0, 10000.0, 37.0)
    assert (p["stop_loss"], p["target"], p["original_exit_date"], p["planned_exit_date"]) == (90.0, 120.0, "2026-11-11", "2026-11-11")
    assert (p["status"], p["opened_on"], p["last_mark_date"], p["pnl"], p["days_held"]) == ("open", OPEN_DAY, OPEN_DAY, 0.0, 0)
    assert (p["stage"], p["signal"], p["needs_review"]) == ("Breakout", "🔵 Breakout Confirmed", False)
    d = client.get(f"/api/v1/positions/{p['id']}").json()
    assert [e["event_type"] for e in d["events"]] == ["open"] and d["events"][0]["new_exit_date"] == "2026-11-11"
    assert d["marks"] == [{"mark_date": OPEN_DAY, "close": 123.0, "value": 9963.0, "pnl": 0.0, "pnl_pct": 0.0}]
    assert d["suggestion"]["id"] == sid and d["suggestion"]["is_tracked"] is True and d["suggestion"]["position_id"] == p["id"]
    assert d["benchmark"] == {"symbol": "NIFTY 50", "change_pct_since_open": 0.0}  # window ends at the last mark
    world["set"]("2026-11-20")
    _mark("2026-11-20")
    assert client.get(f"/api/v1/positions/{p['id']}").json()["benchmark"]["change_pct_since_open"] == 3.0


def test_open_validation(client, world):
    pid = world["pid"]
    sid = world["suggest"](pid, "AAA")
    assert _open(client, pid, sid, capital=50).status_code == 400              # cannot buy one share
    assert _open(client, pid).status_code == 400                                # neither id nor symbol
    assert _open(client, pid, 99999).status_code == 404
    assert _open(client, pid, sid, symbol="BBB").status_code == 400             # mismatch
    other = client.post("/api/v1/profiles", json={"name": "Other", "owner": "x"}).json()["id"]
    assert _open(client, other, sid).status_code == 400                         # suggestion of another profile
    assert _open(client, pid, sid).status_code == 201
    assert _open(client, pid, symbol="aaa").status_code == 409                  # already tracked
    assert _open(client, pid, symbol="ZZZ").status_code == 404


def test_bare_symbol_builds_a_plan(client, world):
    world["set"](OPEN_DAY, CCC={d.date().isoformat(): 100 + i * 0.3 for i, d in enumerate(DAYS[DAYS <= OPEN_DAY])})
    p = _open(client, world["pid"], symbol="CCC", capital=5000).json()
    assert p["suggestion_id"] is None and p["capital"] == 5000.0
    assert p["stop_loss"] < p["entry_price"] < p["target"] and p["planned_exit_date"] > OPEN_DAY


def test_mark_closes_on_target_and_stop_with_catch_up(client, world):
    pid = world["pid"]
    a = _open(client, pid, world["suggest"](pid, "AAA")).json()["id"]
    b = _open(client, pid, world["suggest"](pid, "BBB")).json()["id"]
    # AAA hits target on 11-06; BBB hits stop on 11-09; the job only runs on 11-10 (missed days are caught up).
    world["set"]("2026-11-10", AAA={"2026-11-05": 110.0, "2026-11-06": 121.0, "2026-11-09": 80.0},
                 BBB={"2026-11-05": 95.0, "2026-11-06": 92.0, "2026-11-09": 89.0, "2026-11-10": 130.0})
    summary = _mark("2026-11-10")
    assert summary == {"marked": 2, "closed_target": 1, "closed_stop": 1, "marked_due": 0}
    pa = client.get(f"/api/v1/positions/{a}").json()
    assert (pa["status"], pa["close_reason"], pa["closed_on"], pa["exit_price"]) == ("closed", "target_hit", "2026-11-06", 121.0)
    assert pa["pnl"] == 2100.0 and pa["pnl_pct"] == 21.0 and pa["current_value"] == 12100.0
    assert [m["mark_date"] for m in pa["marks"]] == [OPEN_DAY, "2026-11-05", "2026-11-06"]  # nothing after close
    assert pa["events"][-1]["event_type"] == "close" and "Target ₹120 reached" in pa["events"][-1]["reason"]
    pb = client.get(f"/api/v1/positions/{b}").json()
    assert (pb["close_reason"], pb["closed_on"], pb["pnl"], pb["needs_review"]) == ("stop_hit", "2026-11-09", -1100.0, True)
    assert _mark("2026-11-10") == {"marked": 0, "closed_target": 0, "closed_stop": 0, "marked_due": 0}  # idempotent


def test_due_extend_shorten_close(client, world):
    pid = world["pid"]
    pos = _open(client, pid, world["suggest"](pid, "AAA", exit_date="2026-11-06")).json()["id"]
    world["set"]("2026-11-09", AAA={"2026-11-09": 105.0})
    assert _mark("2026-11-09")["marked_due"] == 1
    p = client.get(f"/api/v1/positions/{pos}").json()
    assert p["status"] == "due" and [e["event_type"] for e in p["events"]] == ["open", "due"]
    assert p["events"][1]["event_date"] == "2026-11-06"  # due on the exit day itself, found during catch-up
    assert _mark("2026-11-09")["marked_due"] == 0

    url = f"/api/v1/positions/{pos}"
    assert client.post(f"{url}/extend", json={"new_exit_date": "2026-11-06", "reason": "x"}).status_code == 400
    assert client.post(f"{url}/extend", json={"new_exit_date": "2026-11-20", "reason": "  "}).status_code == 400
    assert client.post(f"{url}/extend", json={"new_exit_date": "20-11-2026", "reason": "x"}).status_code == 400
    r = client.post(f"{url}/extend", json={"new_exit_date": "2026-11-20", "reason": "Results due on 18 Nov"})
    assert r.status_code == 200
    p = r.json()
    assert (p["status"], p["planned_exit_date"], p["original_exit_date"]) == ("open", "2026-11-20", "2026-11-06")
    ext = p["events"][-1]
    assert (ext["event_type"], ext["old_exit_date"], ext["new_exit_date"], ext["reason"]) == \
        ("extend", "2026-11-06", "2026-11-20", "Results due on 18 Nov")

    assert client.post(f"{url}/shorten", json={"new_exit_date": "2026-11-20", "reason": "x"}).status_code == 400
    assert client.post(f"{url}/shorten", json={"new_exit_date": "2026-11-13", "reason": ""}).status_code == 400
    p = client.post(f"{url}/shorten", json={"new_exit_date": "2026-11-09", "reason": "Sector weak"}).json()
    assert p["status"] == "due"  # new date already reached
    assert client.post(f"{url}/notes", json={"note": "Watching volume"}).json()["events"][-1]["reason"] == "Watching volume"
    assert client.post(f"{url}/notes", json={"note": ""}).status_code == 400

    assert client.post(f"{url}/close", json={"reason": ""}).status_code == 400
    p = client.post(f"{url}/close", json={"reason": "Horizon reached"}).json()
    assert (p["status"], p["close_reason"], p["exit_price"], p["closed_on"]) == ("closed", "horizon_closed", 105.0, "2026-11-09")
    assert p["days_to_exit"] is None and p["days_held"] == 3
    assert client.post(f"{url}/close", json={"reason": "again"}).status_code == 409
    assert client.post(f"{url}/extend", json={"new_exit_date": "2026-12-01", "reason": "x"}).status_code == 409
    assert client.get("/api/v1/positions/99999").status_code == 404


def test_manual_close_of_open_position(client, world):
    pid = world["pid"]
    pos = _open(client, pid, world["suggest"](pid, "AAA")).json()["id"]
    world["set"]("2026-11-05", AAA={"2026-11-05": 104.0})
    p = client.post(f"/api/v1/positions/{pos}/close", json={"reason": "Booked early"}).json()
    assert (p["close_reason"], p["exit_price"], p["pnl"]) == ("manual", 104.0, 400.0)
    flat = _open(client, pid, world["suggest"](pid, "BBB")).json()["id"]
    assert client.post(f"/api/v1/positions/{flat}/close", json={"reason": "same day"}).text.count('-0.0') == 0  # never -0.0
    assert p["events"][-1]["reason"] == "Booked early"


def test_list_filter_and_stats(client, world):
    pid = world["pid"]
    win = _open(client, pid, world["suggest"](pid, "AAA")).json()["id"]
    loss = _open(client, pid, world["suggest"](pid, "BBB", exit_date="2026-11-06")).json()["id"]
    live = _open(client, pid, world["suggest"](pid, "CCC")).json()["id"]
    ext = _open(client, pid, world["suggest"](pid, "DDD", exit_date="2026-11-06")).json()["id"]
    world["set"]("2026-11-06", AAA={"2026-11-06": 125.0}, BBB={"2026-11-05": 85.0}, CCC={"2026-11-06": 110.0},
                 DDD={"2026-11-06": 104.0})
    _mark("2026-11-06")
    # DDD is due at 104 on its original exit day; extend it and let it fall to the stop -> extension hurt.
    client.post(f"/api/v1/positions/{ext}/extend", json={"new_exit_date": "2026-11-20", "reason": "Give it time"})
    world["set"]("2026-11-10", DDD={"2026-11-10": 89.0}, CCC={"2026-11-09": 110.0, "2026-11-10": 110.0})
    _mark("2026-11-10")

    assert [p["id"] for p in client.get(f"/api/v1/profiles/{pid}/positions").json()] == [ext, live, loss, win]
    assert [p["id"] for p in client.get(f"/api/v1/profiles/{pid}/positions?status=open").json()] == [live]
    assert client.get(f"/api/v1/profiles/{pid}/positions?status=weird").status_code == 400

    s = client.get(f"/api/v1/profiles/{pid}/stats").json()
    assert (s["open"], s["due"], s["closed"], s["wins"], s["losses"]) == (1, 0, 3, 1, 2)
    assert s["win_rate_pct"] == pytest.approx(33.33)
    assert s["realised_pnl"] == 2500.0 - 1500.0 - 1100.0
    assert s["unrealised_pnl"] == 1000.0 and s["total_pnl"] == s["realised_pnl"] + 1000.0
    assert s["total_invested"] == 40000.0
    assert s["best"] == {"symbol": "AAA", "pnl_pct": 25.0} and s["worst"] == {"symbol": "BBB", "pnl_pct": -15.0}
    assert s["closed_by"] == {"target_hit": 1, "stop_hit": 2, "horizon_closed": 0, "manual": 0}
    assert s["extensions"] == {"count": 1, "helped": 0, "hurt": 1}
    assert s["avg_win_pct"] == 25.0 and s["avg_loss_pct"] == pytest.approx(-13.0)
    assert s["pending_reviews"] == 2


def test_empty_stats(client, world):
    s = client.get(f"/api/v1/profiles/{world['pid']}/stats").json()
    assert s["win_rate_pct"] is None and s["best"] is None and s["total_pnl"] == 0.0
    assert client.get("/api/v1/profiles/999/stats").status_code == 404


CA_NOTE = ("Possible corporate action (split/bonus/consolidation): price moved -60% in one day. "
           "Auto-close suspended; review manually.")


def test_split_suspends_auto_close_until_user_acts(client, world):
    pid = world["pid"]
    pos = _open(client, pid, world["suggest"](pid, "AAA", stop=90.0, target=120.0, exit_date="2026-11-30")).json()["id"]
    # 1:2.5 split on 11-05: close 100 -> 40 (far below the stop). Next day still "below stop".
    world["set"]("2026-11-06", AAA={"2026-11-05": 40.0, "2026-11-06": 41.0})
    assert _mark("2026-11-06") == {"marked": 1, "closed_target": 0, "closed_stop": 0, "marked_due": 0}
    p = client.get(f"/api/v1/positions/{pos}").json()
    assert p["status"] == "open" and p["last_close"] == 41.0
    note = p["events"][-1]
    assert (note["event_type"], note["event_date"], note["reason"], note["price"]) == ("note", "2026-11-05", CA_NOTE, 40.0)
    assert [m["mark_date"] for m in p["marks"]] == [OPEN_DAY, "2026-11-05", "2026-11-06"]  # still marked daily

    # A plain note does not lift the suspension.
    client.post(f"/api/v1/positions/{pos}/notes", json={"note": "Checking NSE corporate actions"})
    world["set"]("2026-11-09", AAA={"2026-11-09": 40.5})
    assert _mark("2026-11-09")["closed_stop"] == 0

    # After the user extends (same trading day counts), normal auto-close resumes.
    client.post(f"/api/v1/positions/{pos}/extend", json={"new_exit_date": "2026-12-15", "reason": "Split 1:2.5, reviewed"})
    world["set"]("2026-11-10", AAA={"2026-11-10": 39.0})
    assert _mark("2026-11-10")["closed_stop"] == 1
    assert client.get(f"/api/v1/positions/{pos}").json()["close_reason"] == "stop_hit"


def test_consolidation_suspends_target_and_manual_close_still_works(client, world):
    pid = world["pid"]
    pos = _open(client, pid, world["suggest"](pid, "BBB", stop=90.0, target=120.0)).json()["id"]
    world["set"]("2026-11-05", BBB={"2026-11-05": 940.0})  # 10:1 consolidation looks like +840%
    _mark("2026-11-05")
    p = client.get(f"/api/v1/positions/{pos}").json()
    assert p["status"] == "open" and "price moved +840% in one day" in p["events"][-1]["reason"]
    closed = client.post(f"/api/v1/positions/{pos}/close", json={"reason": "Consolidation; closing to re-enter"}).json()
    assert (closed["status"], closed["close_reason"]) == ("closed", "manual")


def test_ordinary_moves_do_not_trigger(client, world):
    pid = world["pid"]
    pos = _open(client, pid, world["suggest"](pid, "CCC", stop=60.0, target=200.0)).json()["id"]
    world["set"]("2026-11-05", CCC={"2026-11-05": 139.0})  # +39%: big but under the threshold
    _mark("2026-11-05")
    assert all(e["event_type"] != "note" for e in client.get(f"/api/v1/positions/{pos}").json()["events"])
