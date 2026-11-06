"""Verdict (docs/API_CONTRACT.md -> Verdict): the three overall outcomes, trend/label/points/reason wording, rule
counting that excludes skipped filters, presence on every surface, backfill for older rows. No network.
"""
import json

import pytest

from app.engine.scoring.signal import SIGNALS
from app.services.analysis_service import build_verdict, chart_trend
from tests.test_suggestion_runs import BUNDLES, STRONG_INFO, _profile, _run, market  # noqa: F401  (fixture)

EARLY, BREAKOUT, DEVELOPING, WEAK = (SIGNALS[k] for k in ("EARLY_SETUP", "BREAKOUT_CONFIRMED", "DEVELOPING", "WEAK"))


def v(failures=(), total=9, signal=BREAKOUT, stage="Breakout", trend="STRONG_UPTREND", rsi=61.2, vol=1.53, profit=42.0):
    return build_verdict(list(failures), total, signal, stage, trend, rsi, vol, profit)


# --- the three outcomes -------------------------------------------------------------------------

def test_buy_needs_all_rules_uptrend_and_a_good_signal():
    out = v()
    assert out == {
        "overall": "buy",
        "rules": {"passed": 9, "total": 9, "failures": []},
        "chart": {"trend": "uptrend", "label": "Uptrend, breakout confirmed",
                  "points": ["Above 200-day EMA", "RSI 61", "Volume 1.5x"]},
        "reason": "Passes all rules; Uptrend, breakout confirmed.",
    }
    for signal in (EARLY, DEVELOPING):
        assert v(signal=signal, stage="Quiet Accumulation")["overall"] == "buy"


@pytest.mark.parametrize("why, kwargs", [
    ("one rule fails", {"failures": ["P/E 62 above max 50"]}),
    ("two rules fail", {"failures": ["P/E 62 above max 50", "RSI 74 above max 70"]}),
    ("sideways chart", {"trend": None}),
    ("extended signal", {"signal": SIGNALS["EXTENDED"], "stage": "Extended"}),
])
def test_watch_otherwise(why, kwargs):
    assert v(**kwargs)["overall"] == "watch", why


@pytest.mark.parametrize("why, kwargs", [
    ("weak signal", {"signal": WEAK}),
    ("downtrend", {"trend": "BELOW_200EMA (bearish bias)"}),
    ("profit falling", {"profit": -0.5}),
    ("more than two failures", {"failures": ["a", "b", "c"]}),
])
def test_avoid(why, kwargs):
    assert v(**kwargs)["overall"] == "avoid", why


def test_avoid_example_from_the_contract():
    out = v(failures=["P/E 243 above max 50", "Profit growth -81% below min 20%"], signal=WEAK, stage="Momentum",
            trend="BELOW_200EMA (bearish bias)", rsi=50.0, vol=1.5, profit=-81.0)
    assert out["overall"] == "avoid" and out["rules"] == {"passed": 7, "total": 9, "failures":
                                                          ["P/E 243 above max 50", "Profit growth -81% below min 20%"]}
    assert out["chart"] == {"trend": "downtrend", "label": "Downtrend, weak",
                            "points": ["Below 200-day EMA", "RSI 50", "Volume 1.5x"]}
    assert out["reason"] == "P/E 243 above max 50; Downtrend, weak."


# --- wording ----------------------------------------------------------------------------------------

@pytest.mark.parametrize("ema_trend, trend", [
    ("STRONG_UPTREND", "uptrend"), ("ABOVE_200EMA (bullish bias)", "uptrend"), ("UPTREND", "uptrend"),
    ("STRONG_DOWNTREND", "downtrend"), ("BELOW_200EMA (bearish bias)", "downtrend"), ("DOWNTREND", "downtrend"),
    (None, "sideways"), ("", "sideways"),
])
def test_trend_mapping(ema_trend, trend):
    assert chart_trend(ema_trend) == trend


def test_label_uses_stage_unless_the_signal_says_more():
    assert v(signal=EARLY, stage="Quiet Accumulation", trend=None)["chart"]["label"] == "Sideways, quiet accumulation"
    assert v(signal=DEVELOPING, stage="Volume Expansion")["chart"]["label"] == "Uptrend, volume expansion"
    assert v(signal=WEAK, trend="DOWNTREND")["chart"]["label"] == "Downtrend, weak"


def test_points_skip_what_is_unavailable_and_use_50ema_without_200():
    assert v(trend="UPTREND", rsi=None, vol=None)["chart"]["points"] == ["Above 50-day EMA"]
    assert v(trend=None, rsi=None, vol=None)["chart"]["points"] == []


# --- end to end ---------------------------------------------------------------------------------------

def test_rules_total_excludes_skipped_filters_and_verdict_is_everywhere(client, market, monkeypatch):  # noqa: F811
    from app.services import suggestion_service

    monkeypatch.setattr(suggestion_service, "_spawn_watchlist", suggestion_service.execute_watchlist_run)
    pid = _profile(client)
    _run(client, pid)
    item = client.get(f"/api/v1/profiles/{pid}/suggestions").json()["items"][0]
    detail = client.get(f"/api/v1/suggestions/{item['id']}").json()
    # 13 profile filters minus the 200-day EMA one (synthetic history is too short) + corporate-action + fundamentals
    assert detail["filters"]["failures"] == ["200-day EMA unavailable, filter skipped"]
    assert detail["verdict"]["rules"] == {"passed": 14, "total": 14, "failures": []}  # the skip is neither
    assert item["verdict"] == detail["verdict"]

    explore = client.post(f"/api/v1/stocks/PRICEYCO/analyze?profile_id={pid}").json()
    assert explore["verdict"]["rules"] == {"passed": 13, "total": 14, "failures": ["P/E 95 above max 50"]}
    assert explore["verdict"]["overall"] == "watch"
    assert explore["verdict"]["reason"].startswith("P/E 95 above max 50; ")

    wl = client.post(f"/api/v1/profiles/{pid}/watchlist-runs", json={"symbols": ["GOODCO", "NOPE"]}).json()
    hit, miss = client.get(f"/api/v1/runs/{wl['id']}/results").json()["items"]
    assert hit["verdict"]["rules"]["total"] == 14 and "verdict" not in miss  # WatchlistMiss has no verdict


def test_verdict_backfilled_once_for_older_rows(client, market):  # noqa: F811
    from app.db.session import SessionLocal
    from app.models import Suggestion

    pid = _profile(client)
    _run(client, pid)
    sid = client.get(f"/api/v1/profiles/{pid}/suggestions").json()["items"][0]["id"]
    original = client.get(f"/api/v1/suggestions/{sid}").json()["verdict"]
    with SessionLocal() as db:  # simulate a row saved before verdicts existed
        row = db.get(Suggestion, sid)
        payload = json.loads(row.payload_json)
        payload.pop("verdict")
        row.payload_json = json.dumps(payload)
        db.commit()
    assert client.get(f"/api/v1/profiles/{pid}/suggestions").json()["items"][0]["verdict"] == original  # recomputed
    with SessionLocal() as db:
        assert json.loads(db.get(Suggestion, sid).payload_json)["verdict"] == original  # and saved


def test_missing_market_cap_skips_the_cap_filter(client, market, monkeypatch):  # noqa: F811
    no_cap = {k: val for k, val in STRONG_INFO.items() if k != "marketCap"}
    monkeypatch.setitem(BUNDLES, "GOODCO", {**BUNDLES["GOODCO"], "info": no_cap})
    pid = _profile(client)
    d = client.post(f"/api/v1/stocks/GOODCO/analyze?profile_id={pid}").json()
    assert d["filters"] == {"passed": True, "failures": ["Market cap unavailable, filter skipped",
                                                         "200-day EMA unavailable, filter skipped"]}
    assert d["verdict"]["rules"] == {"passed": 13, "total": 13, "failures": []}  # one rule fewer, not a failure
    assert d["market_cap_bucket"] == "Unknown"


# --- reason wording (contract: three sentences, word for word) ------------------------------------

@pytest.mark.parametrize("kwargs, reason", [
    ({"failures": ["P/E 62 above max 50"]}, "P/E 62 above max 50; Uptrend, breakout confirmed."),             # failure
    ({}, "Passes all rules; Uptrend, breakout confirmed."),                                                     # buy
    ({"trend": None, "signal": EARLY, "stage": "Quiet Accumulation"},
     "Passes all rules; Sideways, quiet accumulation."),                                                        # watch
    ({"trend": "BELOW_200EMA (bearish bias)", "signal": DEVELOPING, "stage": "Volume Expansion"},
     "Passes all rules, but the chart is downtrend: Downtrend, volume expansion."),                            # avoid
    ({"signal": WEAK}, "Passes all rules, but the chart is uptrend: Uptrend, weak."),                          # avoid
    ({"profit": -12.0, "trend": None}, "Passes all rules, but the chart is sideways: Sideways, breakout confirmed."),
])
def test_reason_sentences(kwargs, reason):
    out = v(**kwargs)
    assert out["reason"] == reason
    if not out["rules"]["failures"] and out["overall"] == "avoid":
        assert out["reason"].startswith("Passes all rules, but the chart is ")


def test_stored_reason_is_rebuilt_with_current_wording(client, market):  # noqa: F811
    from app.db.session import SessionLocal
    from app.models import Suggestion

    pid = _profile(client)
    _run(client, pid)
    sid = client.get(f"/api/v1/profiles/{pid}/suggestions").json()["items"][0]["id"]
    with SessionLocal() as db:  # a verdict stored with an older wording, and turned into a no-failure avoid
        row = db.get(Suggestion, sid)
        payload = json.loads(row.payload_json)
        payload["verdict"].update(overall="avoid", reason="Passes all rules; old wording.")
        payload["verdict"]["rules"]["failures"] = []
        payload["verdict"]["chart"].update(trend="downtrend", label="Downtrend, weak")
        row.payload_json = json.dumps(payload)
        db.commit()
    for path in (f"/api/v1/suggestions/{sid}", f"/api/v1/profiles/{pid}/suggestions"):
        body = client.get(path).json()
        verdict = body["verdict"] if "verdict" in body else body["items"][0]["verdict"]
        assert verdict["reason"] == "Passes all rules, but the chart is downtrend: Downtrend, weak.", path
