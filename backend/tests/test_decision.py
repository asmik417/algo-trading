"""Decision (docs/API_CONTRACT.md -> Decision): expectation and review for every overall x trend, the trigger for each
rule failure, findings rules, headline templates, confidence from the latest finished backtest, the narrative
(prompt holds no number absent from the material; invented numbers rejected; cached), and the API surfaces.
"""
import json
import re

import pytest

from app.engine.agents import decision_narrator
from app.engine.scoring.signal import SIGNALS
from app.services import decision_service as ds
from app.services.plan_service import exit_date_after
from tests.test_suggestion_runs import _profile, _run, market  # noqa: F401  (fixture)

DAY = "2026-11-04"
IN_20 = exit_date_after(DAY, 20)


def ctx(**kw):
    base = {"symbol": "ACME", "price": 500.0, "score": 72.0, "signal": SIGNALS["BREAKOUT_CONFIRMED"], "stage": "Breakout",
            "entry_optimal": 480.0, "stop": 440.0, "target": 620.0, "planned_exit_date": "2026-12-15",
            "trading_day": DAY, "ema_trend": "STRONG_UPTREND", "ema200": 410.0, "ema50": 460.0, "rsi": 61.0,
            "volume_ratio": 1.6, "macd_signal": "BULLISH", "pe": 25.0, "latest_ocf": 5e9, "market_cap": 3e11,
            "profit_yoy_pct": 42.0, "deliv_recent": 55.0, "deliv_prior": 50.0, "low_20d": 452.0, "high_52w": 540.0,
            "macd_hist": 1.2}
    base.update(kw)
    return base


def decide(overall, trend, failures=(), **kw):
    c = ctx(**kw)
    texts = [ds.rule_finding(f, c) for f in failures]
    exp = ds.expectation(overall, trend, list(failures), texts, c)
    return exp, ds.review(overall, trend, list(failures), c, exp["by_date"])


# --- expectation + review: every overall x trend combination ---------------------------------------------------
# (buy always has an uptrend; a downtrend always makes the verdict avoid, so these are all six that can occur)

def test_buy_uptrend():
    exp, rev = decide("buy", "uptrend")
    assert exp == {"direction": "up", "level": 620.0, "by_date": "2026-12-15",
                   "text": "Expect ₹620 by 15 Dec 2026 while it holds above ₹440."}
    assert rev == {"until": "2026-12-15", "trigger": "it closes below the stop at ₹440"}


def test_watch_uptrend_with_a_failure():
    exp, rev = decide("watch", "uptrend", ["RSI 74 above max 70"])
    assert exp == {"direction": "sideways", "level": 480.0, "by_date": IN_20,
                   "text": "Expect a pullback toward ₹480; becomes a Buy if it holds there and RSI drops back under 70."}
    assert rev == {"until": IN_20, "trigger": "RSI drops back under 70"}


def test_watch_sideways_without_failures():
    exp, rev = decide("watch", "sideways", ema_trend=None, signal=SIGNALS["EARLY_SETUP"])
    assert exp["direction"] == "sideways" and exp["level"] == 480.0 and exp["by_date"] == IN_20
    assert exp["text"].endswith("and it closes above the 200-day EMA (₹410).")
    assert rev == {"until": IN_20, "trigger": "it closes above the 200-day EMA (₹410)"}


def test_avoid_downtrend():
    exp, rev = decide("avoid", "downtrend", ["Price is below the 200-day EMA"], ema_trend="BELOW_200EMA (bearish bias)",
                      low_20d=452.0)
    assert exp == {"direction": "down", "level": 452.0, "by_date": IN_20,
                   "text": "Expect further weakness toward ₹452 over the next 4 weeks."}   # max(stop 440, 20-day low 452)
    assert rev == {"until": IN_20, "trigger": "it closes above the 200-day EMA (₹410)"}
    exp2, _ = decide("avoid", "downtrend", low_20d=400.0)
    assert exp2["level"] == 440.0                                                         # the stop is higher


def test_avoid_uptrend():
    exp, rev = decide("avoid", "uptrend", ["P/E 95 above max 50", "ROE 8.0% below min 15%", "Volume 0.50x 20-day average, below min 1.20x"])
    assert exp == {"direction": "sideways", "level": None, "by_date": IN_20,
                   "text": "The price may hold up, but the numbers do not support buying: P/E 95 above max 50."}
    assert rev == {"until": IN_20, "trigger": "P/E falls under 50 (price below ₹1,000)"}    # 500 x 50 / 25


def test_avoid_sideways_weak_signal_without_failures():
    exp, rev = decide("avoid", "sideways", ema_trend=None, signal=SIGNALS["WEAK"], score=38.0)
    assert exp["level"] is None and exp["text"].endswith("do not support buying: the signal is Weak (score 38 of 100).")
    assert rev == {"until": IN_20, "trigger": "the signal turns to Early Setup or Breakout"}


# --- the trigger for each rule failure (phrased as a condition) ------------------------------------------------------

@pytest.mark.parametrize("failure, trigger", [
    ("Price is below the 200-day EMA", "it closes above the 200-day EMA (₹410)"),
    ("RSI 78 above max 70", "RSI drops back under 70"),
    ("RSI 38 below min 45", "RSI rises back above 45"),
    ("Profit growth 9% below min 20%", "the next quarterly results show profit growth of 20% or more"),
    ("Volume 0.85x 20-day average, below min 1.20x", "volume runs above 1.2× its average for 3 sessions"),
    ("P/E 95 above max 50", "P/E falls under 50 (price below ₹1,000)"),
    ("P/E -12 is negative (loss-making)", "the company returns to profit (a positive P/E)"),
    ("ROE 8.8% below min 15%", "ROE reaches 15% or more in the next annual results"),
    ("Debt/equity 180% above max 100%", "debt/equity falls under 100%"),
    ("Operating cash flow is negative", "operating cash flow turns positive in the next annual results"),
    ("3-month run-up 74% above max 50%", "the 3-month gain cools to under 50%"),
    ("32% below 52-week high, more than max 25%", "it climbs back within 25% of its 52-week high (above ₹405)"),
    ("Score 51 below min 65", "its score reaches 65"),
    (f"Signal is {SIGNALS['WEAK']}", "the signal turns to Early Setup or Breakout"),
    ("Market cap bucket Small Cap not in allowed (Large Cap)", "its market cap moves into an allowed bucket (Large Cap)"),
    ("Possible corporate action on 2026-10-22, excluded",
     "130 sessions have passed since the possible corporate action on 2026-10-22"),
    ("No fundamentals available (ETF, fund or data missing)", "fundamentals become available"),
    ("Nifty 50 is 3.4% below its 50-day EMA, more than max 2%: no new picks today",
     "Nifty 50 climbs back within 2% of its 50-day EMA"),
])
def test_trigger_per_failure(failure, trigger):
    assert ds.rule_fix(failure, ctx()) == trigger
    assert re.search(r"\d", ds.rule_finding(failure, ctx()))     # and its finding carries a figure


# --- findings and headline ----------------------------------------------------------------------------------------------

POSITIVES = ["Profit growth (42%) is far outpacing revenue growth (18%) — margin expansion, not just volume.",
             "Low leverage.", "Trend: Strong Uptrend.", "Volume running at 1.6x its 20-day average."]


def test_findings_failed_rules_first_with_figures_and_bounds():
    failures = ["P/E 95 above max 50", "Price is below the 200-day EMA", "RSI 78 above max 70", "Score 51 below min 65"]
    f = ds.findings("avoid", failures, POSITIVES, ctx(ema_trend="BELOW_200EMA", rsi=78.0, deliv_recent=40.0,
                                                    deliv_prior=51.0, macd_signal="BEARISH", macd_hist=-2.31))
    assert [x["text"] for x in f[:3]] == ["P/E 95 above max 50", "Price ₹500 is below its 200-day EMA ₹410",
                                          "RSI 78 above max 70"]                       # max 3, in the verdict's order
    assert "Delivery % fell from 51% to 40% over the last 10 sessions" in [x["text"] for x in f]
    assert all(re.search(r"\d", x["text"]) for x in f) and 3 <= len(f) <= 6
    assert not any("Low leverage" in x["text"] or "Trend:" in x["text"] for x in f)   # bare adjectives never appear
    assert not any("skipped" in x["text"] for x in f)
    assert sum(1 for x in f if "200-day EMA" in x["text"]) == 1                       # not repeated as a chart point


def test_buy_findings_lead_with_positives_and_are_padded_to_three():
    f = ds.findings("buy", [], POSITIVES, ctx())
    assert f[0] == {"side": "for", "text": "Profit growth (42%) is far outpacing revenue growth (18%) — margin "
                                           "expansion, not just volume"}
    thin = ds.findings("buy", [], [], ctx(ema_trend=None, deliv_recent=None))
    assert len(thin) == 3 and all(re.search(r"\d", x["text"]) for x in thin)          # padded with figures


def test_headlines():
    c = ctx()
    finds = ds.findings("buy", [], POSITIVES, c)
    assert ds.headline("buy", "Uptrend, breakout confirmed", "uptrend", finds, [], c) == \
        "Buy ACME near ₹480: Uptrend, breakout confirmed, profit growth (42%) is far outpacing revenue growth (18%)."
    assert ds.headline("watch", "Uptrend, breakout confirmed", "uptrend", finds, ["RSI 78 above max 70"], c) == \
        "Wait on ACME: RSI 78 above max 70."
    assert ds.headline("watch", "Sideways, quiet accumulation", "sideways", finds, [], c) == \
        "Wait on ACME: the chart is sideways (Sideways, quiet accumulation)."
    assert ds.headline("avoid", "Downtrend, weak", "downtrend", finds, ["P/E 243 above max 50"], c) == \
        "Avoid ACME for now: P/E 243 above max 50; Downtrend, weak."


# --- narrative -------------------------------------------------------------------------------------------------------------

def _material():
    c = ctx()
    finds = ds.findings("watch", ["RSI 78 above max 70"], POSITIVES, c)
    head = ds.headline("watch", "Uptrend, breakout confirmed", "uptrend", finds, ["RSI 78 above max 70"], c)
    exp, rev = decide("watch", "uptrend", ["RSI 78 above max 70"])
    return head, finds, exp, {**rev, "until_text": "02 Dec 2026"}


def test_narrative_prompt_contains_no_number_absent_from_the_findings():
    head, finds, exp, rev = _material()
    system, user = decision_narrator.build_prompt(head, finds, exp, rev)
    assert not re.search(r"\d", system)                                   # instructions carry no numbers at all
    given = decision_narrator.numbers_in(" ".join([head, exp["text"], rev["trigger"], rev["until_text"]]
                                                  + [f["text"] for f in finds]))
    assert decision_narrator.numbers_in(user) <= given                     # only the material's own numbers
    for leak in ("72", "61", "460"):                                      # score, RSI, EMA50: known, but not in the material
        assert leak not in decision_narrator.numbers_in(user)


def test_narrative_rejects_invented_numbers(monkeypatch):
    head, finds, exp, rev = _material()
    monkeypatch.setattr(decision_narrator, "call_llm", lambda s, u: {"narrative": "Wait: RSI is 78, above 70."})
    assert decision_narrator.narrate(head, finds, exp, rev) == "Wait: RSI is 78, above 70."
    monkeypatch.setattr(decision_narrator, "call_llm", lambda s, u: {"narrative": "It could reach ₹999 soon."})
    assert decision_narrator.narrate(head, finds, exp, rev) is None        # 999 is nowhere in the findings
    monkeypatch.setattr(decision_narrator, "call_llm", lambda s, u: {"error": "rate limited"})
    assert decision_narrator.narrate(head, finds, exp, rev) is None


# --- end to end: detail, Explore, watchlist, confidence, caching --------------------------------------------------------

def test_decision_on_every_surface_with_confidence_and_cache(client, market, monkeypatch):  # noqa: F811
    from app.db.session import SessionLocal
    from app.engine import config as engine_config
    from app.models import Backtest, Suggestion
    from app.services import suggestion_service

    monkeypatch.setattr(suggestion_service, "_spawn_watchlist", suggestion_service.execute_watchlist_run)
    pid = _profile(client)
    _run(client, pid)
    sid = client.get(f"/api/v1/profiles/{pid}/suggestions").json()["items"][0]["id"]

    calls = []
    monkeypatch.setattr(engine_config, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(ds.decision_narrator, "narrate", lambda *a: calls.append(1) or "We would buy this one.")
    with SessionLocal() as db:  # two finished backtests and a newer running one: the latest *finished* counts
        for status, rate in (("done", 40.0), ("done", 62.5), ("running", 99.0)):
            db.add(Backtest(profile_id=pid, status=status, start_date="2025-11-05", end_date=DAY, capital_per_trade=1e4,
                            breakdowns_json=json.dumps({"by_signal": [{"key": "🔵 Breakout Confirmed", "trades": 8,
                                                                       "win_rate_pct": rate, "avg_pnl_pct": 1.0,
                                                                       "total_pnl": 1.0}]})))
        db.commit()
        latest_done = max(b.id for b in db.query(Backtest).filter_by(status="done"))

    d = client.get(f"/api/v1/suggestions/{sid}").json()["decision"]
    assert set(d) == {"overall", "headline", "findings", "expectation", "review", "confidence", "narrative"}
    assert d["overall"] == client.get(f"/api/v1/suggestions/{sid}").json()["verdict"]["overall"]
    assert 3 <= len(d["findings"]) <= 6 and all(re.search(r"\d", f["text"]) for f in d["findings"])
    assert d["review"]["until"] == d["expectation"]["by_date"]
    sig = client.get(f"/api/v1/suggestions/{sid}").json()["signal"]
    expected_conf = {"signal_win_rate_pct": 62.5, "trades": 8, "backtest_id": latest_done} \
        if sig == "🔵 Breakout Confirmed" else {"signal_win_rate_pct": None, "trades": 0, "backtest_id": latest_done}
    assert d["confidence"] == expected_conf
    assert d["narrative"] == "We would buy this one." and len(calls) == 1
    client.get(f"/api/v1/suggestions/{sid}")
    assert len(calls) == 1                                                  # cached

    with SessionLocal() as db:  # why_flagged narration must not wipe the cached decision narrative
        row = db.get(Suggestion, sid)
        stored = json.loads(row.narration_json)
        assert "decision" in stored and "why_flagged" in stored

    explore = client.post(f"/api/v1/stocks/PRICEYCO/analyze?profile_id={pid}").json()["decision"]
    assert explore["overall"] in ("watch", "avoid") and explore["findings"][0]["text"] == "P/E 95 above max 50"

    wl = client.post(f"/api/v1/profiles/{pid}/watchlist-runs", json={"symbols": ["GOODCO", "NOPE"]}).json()
    hit, miss = client.get(f"/api/v1/runs/{wl['id']}/results").json()["items"]
    assert hit["decision"]["headline"] and "decision" not in miss
    assert len(calls) == 2                                                  # Explore analyze is a detail: narrated once
    before = len(calls)
    client.get(f"/api/v1/runs/{wl['id']}/results")
    assert len(calls) == before                                              # listing results never calls the LLM


def test_no_backtest_means_null_confidence(client, market):  # noqa: F811
    pid = _profile(client)
    _run(client, pid)
    sid = client.get(f"/api/v1/profiles/{pid}/suggestions").json()["items"][0]["id"]
    d = client.get(f"/api/v1/suggestions/{sid}").json()["decision"]
    assert d["confidence"] == {"signal_win_rate_pct": None, "trades": None, "backtest_id": None}
    assert d["narrative"].startswith(d["headline"])                          # deterministic fallback without a key
