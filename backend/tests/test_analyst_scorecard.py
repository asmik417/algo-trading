"""Brain part 3: the analyst view (the profile's own rules verdict, number audit rejecting a fabricated figure, one
retry, agrees_with_rules, caching, endpoints) and the scorecard (right/wrong per direction, marks at 20/40/60
sessions, hit rate, directional average, grouping, worst misses). The model is faked; no network.
"""
import json
import time

import pytest
from test_brain import DAY, world  # noqa: F401  (the fake market fixture)

from app.db.session import SessionLocal
from app.engine.agents import analyst_agent
from app.models import AnalystViewRow, Position, Suggestion, VerdictLogRow
from app.services import analyst_service, scorecard_service
from app.services.scorecard_service import edge, is_right, scorecard_from

CLEAN = {"observations": ["Close 249.5 on the day."], "anomalies": [], "bull_case": "Trend is up.",
         "bear_case": "Rules say avoid.", "tests": [{"claim": "Uptrend holds", "evidence": "present", "note": "RSI given."}],
         "action": "watch", "direction": "up", "confidence": "medium", "trigger": "A close under the stop.",
         "want_to_know": "Order book."}
FABRICATED = {**CLEAN, "bull_case": "Management guided revenue to ₹9,876 crore next year."}


# --- agrees_with_rules ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("action, rules, expected", [
    ("buy", "buy", True), ("add", "buy", True), ("watch", "buy", False), ("hold", "buy", False),
    ("watch", "watch", True), ("hold", "watch", True), ("buy", "watch", False), ("avoid", "watch", False),
    ("avoid", "avoid", True), ("exit", "avoid", True), ("trim", "avoid", True), ("hold", "avoid", False),
    ("buy", None, None), ("exit", None, None),
])
def test_agrees_with_rules(action, rules, expected):
    assert analyst_service.agrees_with_rules(action, rules) is expected


# --- right / wrong and the scorecard maths ------------------------------------------------------------------------------

@pytest.mark.parametrize("direction, change, right", [
    ("up", 0.01, True), ("up", 0.0, False), ("up", -3.0, False),
    ("down", -0.01, True), ("down", 0.0, False), ("down", 4.0, False),
    ("sideways", 5.0, True), ("sideways", -5.0, True), ("sideways", 5.01, False), ("sideways", -7.0, False),
])
def test_right_per_direction(direction, change, right):
    assert is_right(direction, change) is right


def test_edge_is_change_in_the_direction_of_the_call():
    assert edge("up", 4.0) == 4.0 and edge("down", -6.0) == 6.0 and edge("down", 2.0) == -2.0
    assert edge("sideways", 3.0) is None


def _v(i, source, action, direction, day, signal, change=None, horizon=20):
    marks = [] if change is None else [{"sessions": horizon, "date": "2027-01-01", "close": 1.0, "change_pct": change,
                                        "right": is_right(direction, change)}]
    return {"id": i, "symbol": f"S{i}", "day": day, "source": source, "profile_id": 1, "action": action,
            "direction": direction, "level": None, "close": 100.0, "signal": signal, "marks": marks}


def test_scorecard_maths():
    vs = [_v(1, "rules", "buy", "up", "2026-09-01", "A", 10.0),          # right, edge +10
          _v(2, "rules", "buy", "up", "2026-09-15", "A", -4.0),          # wrong, edge -4
          _v(3, "rules", "avoid", "down", "2026-10-01", "B", -6.0),      # right, edge +6
          _v(4, "analyst", "watch", "sideways", "2026-10-02", None, 2.0),   # right, no edge
          _v(5, "analyst", "watch", "sideways", "2026-10-03", None, -9.0),  # wrong by 4 outside the band
          _v(6, "analyst", "buy", "up", "2026-10-04", "A"),              # not marked yet
          _v(7, "rules", "buy", "up", "2026-10-05", "A", 3.0, horizon=40)]  # marked at 40 only
    card = scorecard_from(vs, 1, "both", 20)
    assert card["total"] == {"key": "total", "verdicts": 7, "marked": 5, "right": 3, "hit_rate_pct": 60.0,
                             "avg_change_pct": 4.0}                     # (10 - 4 + 6) / 3; sideways excluded
    assert {r["key"]: (r["verdicts"], r["marked"], r["right"]) for r in card["by_source"]} == {
        "analyst": (3, 2, 1), "rules": (4, 3, 2)}
    assert {r["key"]: r["avg_change_pct"] for r in card["by_action"]} == {"avoid": 6.0, "buy": 3.0, "watch": None}
    assert {r["key"]: r["verdicts"] for r in card["by_signal"]} == {"A": 4, "B": 1, "No signal": 2}
    assert [r["key"] for r in card["by_month"]] == ["2026-09", "2026-10"]
    assert [w["id"] for w in card["worst"]] == [2, 5]     # both missed by 4 (edge -4; 9 vs the 5 band): older first
    assert scorecard_from(vs, 1, "both", 40)["total"]["hit_rate_pct"] == 100.0
    empty = scorecard_from([], 1, "rules", 60)["total"]
    assert empty["hit_rate_pct"] is None and empty["avg_change_pct"] is None


# --- analyst view --------------------------------------------------------------------------------------------------------

class FakeAnalyst:
    def __init__(self, *answers):
        self.answers, self.calls = list(answers), []

    def __call__(self, evidence, actions, previous=None, bad=None):
        self.calls.append({"evidence": evidence, "actions": actions, "previous": previous, "bad": bad})
        answer = self.answers.pop(0) if self.answers else None
        usage = {**analyst_agent.empty_usage(), "input_tokens": 10_000, "output_tokens": 2_000, "calls": 1}
        return (answer, usage, None if answer else "no answer", "claude-opus-5-5")


VERDICT = {"overall": "avoid", "rules": {"passed": 10, "total": 12, "failures": ["P/E 80 above max 50", "ROE 4%"]},
           "chart": {"trend": "uptrend", "label": "Uptrend, developing", "points": []}, "reason": "x"}


def _suggestion(db, profile_id, overall="avoid", signal="🟡 Developing"):
    row = Suggestion(run_id=None, source="explore", profile_id=profile_id, symbol="AAA", trading_day=DAY, rank=None,
                     score=70.0, stage="Stage 2", signal=signal, price=249.5, entry_aggressive=249.5,
                     entry_optimal=245.0, entry_conservative=240.0, stop_loss=230.0, target=290.0, risk_reward=2.0,
                     horizon_days=25, planned_exit_date="2026-12-10", timing_note="", exit_note="",
                     payload_json=json.dumps({"verdict": {**VERDICT, "overall": overall}}))
    db.add(row)
    db.commit()
    return row


@pytest.fixture()
def profiles(world, client):  # noqa: F811
    active = client.get("/api/v1/profiles").json()[0]["id"]
    other = client.post("/api/v1/profiles", json={"name": "Other", "owner": "T", "params": {}}).json()["id"]
    with SessionLocal() as db:
        _suggestion(db, active, "buy", "🟢 Breakout Confirmed")
        _suggestion(db, other, "avoid")
    analyst_service._failures.clear()
    return active, other


def test_audit_rejects_a_fabricated_number_and_the_retry_fixes_it(profiles, monkeypatch):
    active, other = profiles
    fake = FakeAnalyst(FABRICATED, CLEAN)
    monkeypatch.setattr(analyst_agent, "reason", fake)
    with SessionLocal() as db:
        view = analyst_service.analyze(db, "AAA", DAY, other)
    assert fake.calls[1]["bad"] == ["9,876"] and fake.calls[1]["previous"] == FABRICATED
    assert view["audited"] is True and view["bull_case"] == "Trend is up."
    assert any("9,876" in n for n in view["audit_notes"])
    ev = fake.calls[0]["evidence"]
    assert ev["rules_verdict"]["overall"] == "avoid" and ev["strategy"] == "Other"   # the profile's own verdict
    assert ev["plan"]["target"] == 290.0 and "url" not in json.dumps(ev)
    assert view["agrees_with_rules"] is False and view["horizon_sessions"] == 20     # watch vs rules avoid
    assert fake.calls[0]["actions"] == ["buy", "watch", "avoid"]
    with SessionLocal() as db:
        row = db.query(AnalystViewRow).one()
        assert row.cost_usd == round(2 * (10_000 * 4 + 2_000 * 20) / 1e6, 5)          # two calls at Opus 5.5 prices
        logged = db.query(VerdictLogRow).filter_by(source="analyst").one()
        assert (logged.action, logged.direction, logged.signal, logged.close) == ("watch", "up", "🟡 Developing", 249.5)
        again = analyst_service.analyze(db, "AAA", DAY, other)                       # cached: no third call
    assert len(fake.calls) == 2 and again["id"] == view["id"]


def test_second_fabrication_is_stored_unaudited_and_no_answer_stores_nothing(profiles, monkeypatch):
    active, other = profiles
    monkeypatch.setattr(analyst_agent, "reason", FakeAnalyst(FABRICATED, FABRICATED))
    with SessionLocal() as db:
        view = analyst_service.analyze(db, "AAA", DAY, active)
    assert view["audited"] is False and "still used numbers" in view["audit_notes"][-1]
    assert view["agrees_with_rules"] is False                       # rules (active profile) said buy, analyst watch
    monkeypatch.setattr(analyst_agent, "reason", FakeAnalyst(None))
    with SessionLocal() as db, pytest.raises(RuntimeError):
        analyst_service.analyze(db, "AAA", DAY, other)
    with SessionLocal() as db:
        assert db.query(AnalystViewRow).count() == 1


def test_a_holding_gets_the_holding_vocabulary(profiles, monkeypatch):
    active, _ = profiles
    with SessionLocal() as db:
        db.add(Position(profile_id=active, symbol="AAA", opened_on="2026-10-01", entry_price=200.0, qty=5,
                        invested=1000.0, capital=10000.0, target=260.0, stop_loss=180.0,
                        original_exit_date="2026-11-20", planned_exit_date="2026-11-20", status="open"))
        db.commit()
    fake = FakeAnalyst({**CLEAN, "action": "hold"})
    monkeypatch.setattr(analyst_agent, "reason", fake)
    with SessionLocal() as db:
        view = analyst_service.analyze(db, "AAA", DAY, active)
    assert fake.calls[0]["actions"] == ["add", "hold", "trim", "exit"]
    assert fake.calls[0]["evidence"]["derived"]["holding"]["return_pct"] == 24.75     # (249.5 / 200 - 1) x 100
    assert view["action"] == "hold" and view["agrees_with_rules"] is False            # rules buy: agrees only with buy/add


def test_analyst_endpoints(profiles, client, monkeypatch):
    active, other = profiles
    monkeypatch.setattr(analyst_agent, "reason", FakeAnalyst(CLEAN))
    assert client.get("/api/v1/stocks/AAA/analyst-view").status_code == 404
    r = client.post("/api/v1/stocks/AAA/analyst-view", params={"profile_id": other})
    assert r.status_code == 202 and r.json() == {"status": "queued"}
    for _ in range(100):
        got = client.get("/api/v1/stocks/AAA/analyst-view", params={"profile_id": other})
        if got.status_code == 200:
            break
        time.sleep(0.05)
    assert got.status_code == 200 and got.json()["profile_id"] == other and got.json()["day"] == DAY
    assert client.post("/api/v1/stocks/AAA/analyst-view", params={"profile_id": other}).status_code == 200
    assert client.get("/api/v1/stocks/AAA/analyst-view").status_code == 404           # active profile has none
    assert client.get("/api/v1/stocks/AAA/analyst-view", params={"day": DAY, "profile_id": other}).status_code == 200
    assert client.post("/api/v1/stocks/NOPE/analyst-view", params={"profile_id": other}).status_code == 404


# --- logging and marks on the fake market ---------------------------------------------------------------------------------

def test_rules_verdicts_are_logged_once_and_marked_at_20_40_60(world, client):  # noqa: F811
    from test_brain import DATES

    active = client.get("/api/v1/profiles").json()[0]["id"]
    early = DATES[200].date().isoformat()                       # 99 sessions of history after it
    with SessionLocal() as db:
        row = _suggestion(db, active, "buy")
        row.trading_day, row.price = early, 200.0               # AAA closed at 100 + 0.5 x 200 = 200 that day
        _suggestion(db, active, "avoid").trading_day = early    # same stock, day, profile: not logged twice
        db.commit()
        assert scorecard_service.log_rules_verdicts(db) == 1
        assert scorecard_service.log_rules_verdicts(db) == 0   # the sweep moves on
        assert scorecard_service.mark_all(db) == 3 and scorecard_service.mark_all(db) == 0
    card = client.get("/api/v1/scorecard", params={"profile_id": active, "source": "rules", "horizon": 40}).json()
    assert card["total"] == {"key": "total", "verdicts": 1, "marked": 1, "right": 1, "hit_rate_pct": 100.0,
                             "avg_change_pct": 10.0}            # 200 -> 220 after 40 sessions, a buy
    logged = client.get("/api/v1/scorecard/verdicts", params={"profile_id": active, "symbol": "aaa"}).json()
    assert [(m["sessions"], m["close"], m["change_pct"], m["right"]) for m in logged[0]["marks"]] == [
        (20, 210.0, 5.0, True), (40, 220.0, 10.0, True), (60, 230.0, 15.0, True)]
    assert logged[0]["level"] == 290.0 and logged[0]["direction"] == "up" and logged[0]["signal"] == "🟡 Developing"
    assert client.get("/api/v1/scorecard", params={"horizon": 30}).status_code == 400
    assert client.get("/api/v1/scorecard", params={"source": "x"}).status_code == 400


def test_nightly_builds_views_then_logs_and_marks(profiles, client, monkeypatch):
    from datetime import date

    from app.engine.data.sources import SOURCES
    from app.jobs import nightly_brain
    from app.services import market_brief_service

    class Empty:
        def fetch(self, day, **kw):
            return []

    monkeypatch.setattr(nightly_brain, "MODULES", {s: Empty() for s in SOURCES})
    monkeypatch.setattr(market_brief_service.base_agent, "call_llm", lambda s, u: {"error": "no key"})
    fake = FakeAnalyst(CLEAN)
    monkeypatch.setattr(analyst_agent, "reason", fake)
    client.post("/api/v1/pick-lists", json={"name": "Mine", "symbols": ["AAA"]})
    d = date.fromisoformat(DAY)
    summary = nightly_brain.run(nightly_brain.start_job(d).id, d)
    assert (summary["views_built"], summary["views_failed"]) == (1, 0) and summary["views_cost_usd"] > 0
    assert summary["verdicts_logged"] == 2                      # both profiles' rules verdicts for AAA
    again = nightly_brain.run(nightly_brain.start_job(d).id, d)
    assert again["views_built"] == 1 and len(fake.calls) == 1   # cached view: no second model call
    brain = client.get("/api/v1/jobs/status").json()["brain"]
    assert (brain["views_built"], brain["views_failed"]) == (1, 0)
    with SessionLocal() as db:
        assert {r.source for r in db.query(VerdictLogRow)} == {"rules", "analyst"}
