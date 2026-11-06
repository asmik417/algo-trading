"""Brain part 2: the number audit, the regime rules, the market brief (deterministic facts, model text audited with one
retry, deterministic fallback, idempotent) and evidence packs (point-in-time sections; every gap listed in
`unavailable`, never filled with 0), plus their endpoints and the nightly steps. yfinance, NSE and the model are faked.
"""
from datetime import date

import numpy as np
import pandas as pd
import pytest

from app.db.session import SessionLocal
from app.engine.agents.number_audit import numbers_in_text, unsupported_numbers
from app.engine.data import index_history
from app.engine.data.sources import SOURCES, common, news, results
from app.engine.scoring.market_regime import regime
from app.jobs import nightly_brain
from app.services import market_brief_service, market_data, source_service

DAY = "2026-11-05"
D = date(2026, 11, 5)


# --- the number audit (shared with the analyst view) ------------------------------------------------------------------

def test_numbers_in_text_reads_rupees_percent_signs_and_dates():
    found = [raw for raw, _ in numbers_in_text("₹1,23,456.70 cr, -2.3% and −4%; on 2026-11-05 it was 17.4.")]
    assert found == ["1,23,456.70", "2.3", "4", "2026", "11", "05", "17.4"]


def test_audit_accepts_copied_rounded_and_within_one_percent_and_flags_the_rest():
    evidence = {"close": 724.65, "pct": -1.44, "note": "Nifty is 5.41% above its 50-day EMA", "zero": 0, "flag": True}
    ok = "Close 724.65 (about 725, or 724.7), down 1.4% (1.44); 5.41% above the 50-day EMA; 0 deals."
    assert unsupported_numbers([ok], evidence) == []
    assert unsupported_numbers(["Close 731.9"], evidence) == ["731.9"]                 # 1.0 % off: just outside
    assert unsupported_numbers(["Close 731.8"], evidence) == []                        # within ±1 %
    assert unsupported_numbers(["It may reach 999, then 999 again"], evidence) == ["999"]   # listed once
    assert unsupported_numbers(["1 deal"], {"flag": True}) == ["1"]                    # True is not the number 1
    assert unsupported_numbers(["over 20 sessions"], evidence) == ["20"]
    assert unsupported_numbers(["over 20 sessions"], evidence, extra=(20,)) == []
    assert unsupported_numbers(["gap of 6.85 points"], {"a": 5.41, "b": 1.44}) == ["6.85"]  # a sum it computed


# --- regime rules -----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("ema, vix, ad, fii, expected, reasons", [
    (2.0, 12.0, 1.5, [100.0, -50.0, 10.0], "risk_on", ["nifty_above_ema50", "vix_under_15", "breadth_positive"]),
    (-0.5, 12.0, 1.5, None, "risk_off", ["nifty_below_ema50"]),
    (2.0, 21.0, 1.5, None, "risk_off", ["vix_over_20"]),
    (2.0, 12.0, 1.5, [-2500.0, -2100.0, -3000.0], "risk_off", ["fii_heavy_selling"]),
    (2.0, 12.0, 1.5, [-2500.0, -1900.0, -3000.0], "risk_on", ["nifty_above_ema50", "vix_under_15", "breadth_positive"]),
    (2.0, 15.0, 1.5, None, "neutral", ["vix_not_under_15"]),          # 15 is not "under 15"
    (2.0, 20.0, 0.8, None, "neutral", ["vix_not_under_15", "breadth_not_positive"]),   # 20 is not "over 20"
    (-1.0, 25.0, 0.5, [-3000.0] * 3, "risk_off", ["nifty_below_ema50", "vix_over_20", "fii_heavy_selling"]),
])
def test_regime_rules(ema, vix, ad, fii, expected, reasons):
    got, why, _ = regime(ema, vix, ad, fii)
    assert (got, why) == (expected, reasons)


def test_regime_with_missing_inputs_never_guesses():
    assert regime(None, None, None, None) == (
        "neutral", [], ["nifty_vs_ema50_pct", "vix", "advance_decline", "fii_net_3_sessions"])
    assert regime(2.0, None, 1.5, None)[0] == "neutral"             # risk_on needs all three inputs
    assert regime(2.0, 25.0, None, None)[0] == "risk_off"           # a known stress reading is enough
    assert regime(2.0, 12.0, 1.5, [-3000.0, -3000.0])[0] == "risk_on"   # two sessions are not three


# --- a small fake market --------------------------------------------------------------------------------------------------

DATES = pd.bdate_range(end=DAY, periods=300)


def _panel() -> pd.DataFrame:
    rows = []
    paths = {"AAA": 100 + 0.5 * np.arange(300), "CCC": 50 + 0.1 * np.arange(300), "BBB": 300 - 0.3 * np.arange(300)}
    for sym, closes in paths.items():
        for i, (d, c) in enumerate(zip(DATES, closes)):
            rows.append({"symbol": sym, "date": d, "open": c - 1, "high": c + 1, "low": c - 2, "close": float(c),
                         "volume": 3000 if i == 299 else 1000, "turnover_lacs": 50.0, "deliv_qty": 500,
                         "deliv_pct": 60.0 if i == 299 else 40.0})
    return pd.DataFrame(rows).sort_values(["symbol", "date"]).reset_index(drop=True)


NIFTY = pd.Series(20000 + 10.0 * np.arange(300), index=DATES)
SERIES = {"^NSEI": NIFTY, "^INDIAVIX": pd.Series(12.0, index=DATES),
          "^CNXIT": pd.Series(30000 + 50.0 * np.arange(300), index=DATES),
          "^CNXAUTO": pd.Series(25000 - 20.0 * np.arange(300), index=DATES),
          "^CNXFMCG": pd.Series(40000 + 5.0 * np.arange(300), index=DATES)}


@pytest.fixture()
def world(client, monkeypatch):
    def download(ticker):
        if ticker not in SERIES:
            raise RuntimeError("not faked")
        return SERIES[ticker]

    monkeypatch.setattr(index_history, "_download", download)
    monkeypatch.setattr(market_data, "_nifty_closes", lambda: NIFTY)
    monkeypatch.setattr(market_data, "_record_panel_day", lambda day: None)
    for name in ("_panel", "_panel_day", "_histories", "_latest_day"):      # restored after the test
        monkeypatch.setattr(market_data, name, getattr(market_data, name))
    market_data.set_panel(_panel())
    from app.services import evidence_service

    evidence_service._history_tried.clear()
    calls = []

    def fail(*a, **k):
        calls.append(a)
        raise common.SourceUnavailable("network disabled in tests")

    monkeypatch.setattr(results, "symbol_history", fail)
    monkeypatch.setattr(news, "company_items", fail)
    yield calls
    market_data._breadth.clear()


def _store(source, records, day=D):
    with SessionLocal() as db:
        source_service.persist(db, source, day, records)
        source_service.record_pull(db, source, day, "ok" if records else "empty", len(records), len(records), None)


def _market_rows():
    _store("market", [{"key": "fii_net_cr", "date": DAY, "value": -2500.5}, {"key": "dii_net_cr", "date": DAY, "value": 3100.0}])
    _store("global_cues", [{"key": "global:sp500", "date": DAY, "value": 6100.0, "change_1d_pct": 0.42, "change_1w_pct": 1.1},
                           {"key": "global:crude_brent", "date": DAY, "value": 81.5, "change_1d_pct": -0.3, "change_1w_pct": -2.25}])


# --- market brief ---------------------------------------------------------------------------------------------------------

class FakeModel:
    def __init__(self, *replies):
        self.replies, self.prompts = list(replies), []

    def __call__(self, system, user):
        self.prompts.append(user)
        return self.replies.pop(0) if self.replies else {"error": "no more replies"}


def test_brief_facts_regime_and_audited_model_text(world, monkeypatch):
    _market_rows()
    model = FakeModel({"paragraph": "Breadth is strong and FIIs net sold ₹2,500.5 cr.", "stance": "Risk-on; buy with stops."})
    monkeypatch.setattr(market_brief_service.base_agent, "call_llm", model)
    with SessionLocal() as db:
        brief = market_brief_service.build(db, DAY)
    ctx = brief["context"]
    assert brief["regime"] == "risk_on"                     # Nifty rising above its EMA50, VIX 12, 2 of 3 stocks up
    assert ctx["vix"] == 12.0 and ctx["advance_decline"] == 2.0 and ctx["fii_net_cr"] == -2500.5
    assert ctx["nifty_close"] == float(NIFTY.iloc[-1]) and ctx["sp500_1d_pct"] == 0.42 and ctx["crude_1w_pct"] == -2.25
    assert ctx["usdinr_1w_pct"] is None and ctx["sector_index"] is None           # not pulled: None, not 0
    assert [x["index"] for x in brief["leaders"]] == ["NIFTY IT"] and [x["index"] for x in brief["laggards"]] == ["NIFTY AUTO"]
    facts = "\n".join(brief["facts"])
    assert "2 stocks rose and 1 fell (advance/decline 2)" in facts and "FIIs net sold ₹2,500.5 cr" in facts
    assert "Regime: risk-on, because Nifty 50 is above its 50-day EMA" in facts
    assert "Not available for this day: three sessions of FII flows, USD/INR." in facts
    assert brief["paragraph"].startswith("Breadth is strong") and brief["stance"] == "Risk-on; buy with stops."
    assert market_brief_service.is_audited(SessionLocal(), DAY)
    with SessionLocal() as db:
        again = market_brief_service.build(db, DAY)                               # same facts: no new model call
    assert len(model.prompts) == 1 and again["created_at"] == brief["created_at"]


def test_brief_reasks_once_with_the_offending_numbers_then_falls_back(world, monkeypatch):
    _market_rows()
    model = FakeModel({"paragraph": "Nifty could hit 30,000 soon.", "stance": "Buy."},
                      {"paragraph": "The trend is up and breadth is positive.", "stance": "Risk-on; buy with stops."})
    monkeypatch.setattr(market_brief_service.base_agent, "call_llm", model)
    with SessionLocal() as db:
        brief = market_brief_service.build(db, DAY)
    assert "not in the facts: 30,000" in model.prompts[1] and brief["stance"] == "Risk-on; buy with stops."
    assert market_brief_service.is_audited(SessionLocal(), DAY)

    model = FakeModel({"paragraph": "Up 12.5%.", "stance": "x"}, {"paragraph": "Still up 12.5%.", "stance": "x"})
    monkeypatch.setattr(market_brief_service.base_agent, "call_llm", model)
    with SessionLocal() as db:
        text = market_brief_service.write_text(["Nifty 50 closed at 24,536.6."], "neutral")
    assert len(model.prompts) == 2 and text["audited"] is False and text["model"] is None
    assert text["stance"] == market_brief_service.FALLBACK_STANCE["neutral"]
    assert text["paragraph"] == "Nifty 50 closed at 24,536.6." and "12.5" in text["notes"][-1]


def test_brief_without_data_lists_what_is_missing(client, monkeypatch):
    monkeypatch.setattr(market_brief_service.base_agent, "call_llm", lambda s, u: {"error": "no key"})
    monkeypatch.setattr(market_data, "breadth", lambda day: None)          # no bhavcopy panel either
    with SessionLocal() as db:
        brief = market_brief_service.build(db, DAY)
    assert brief["regime"] == "neutral" and brief["leaders"] == [] and brief["laggards"] == []
    assert all(v is None for k, v in brief["context"].items() if k != "day")       # nothing faked
    assert brief["facts"][-1].startswith("Not available for this day: Nifty 50 vs its 50-day EMA, India VIX")
    assert brief["stance"] == market_brief_service.FALLBACK_STANCE["neutral"]


def test_market_brief_api(world, client, monkeypatch):
    monkeypatch.setattr(market_brief_service.base_agent, "call_llm", lambda s, u: {"error": "no key"})
    assert client.get("/api/v1/market/brief").status_code == 404
    with SessionLocal() as db:
        market_brief_service.build(db, "2026-11-04")
        market_brief_service.build(db, DAY)
    latest = client.get("/api/v1/market/brief")
    assert latest.status_code == 200 and latest.json()["day"] == DAY
    assert client.get("/api/v1/market/brief", params={"day": "2026-11-04"}).json()["day"] == "2026-11-04"
    assert client.get("/api/v1/market/brief", params={"day": "2026-10-01"}).status_code == 404
    assert client.get("/api/v1/market/brief", params={"day": "05-11-2026"}).status_code == 400
    assert [b["day"] for b in client.get("/api/v1/market/briefs", params={"limit": 5}).json()] == [DAY, "2026-11-04"]


# --- evidence packs -------------------------------------------------------------------------------------------------------

def _pack(symbol="AAA", day=DAY):
    from app.services import evidence_service

    with SessionLocal() as db:
        return evidence_service.build(db, symbol, day)


def test_pack_with_only_prices_lists_every_gap_and_fakes_nothing(world):
    pack = _pack()
    gaps = set(pack["unavailable"])
    assert {"quarters", "ownership", "deals", "deals.insider", "events", "headlines"} <= gaps
    assert {"market.fii_net_cr", "market.dii_net_cr", "market.sector_index", "market.sp500_1d_pct"} <= gaps
    assert pack["quarters"] == [] and pack["ownership"] is None and pack["deals"] == [] and pack["headlines"] == []
    assert pack["market"]["fii_net_cr"] is None and pack["market"]["vix"] == 12.0
    p = pack["price"]
    assert p["close"] == 249.5 and p["change_1w_pct"] == round((249.5 / 247.0 - 1) * 100, 2)
    assert p["volume_ratio"] is not None and p["delivery_pct_now"] == 60.0 and p["delivery_pct_prev"] == 40.0
    assert p["dist_52w_high_pct"] == 0.0 and p["vs_sector_1m_pct"] is None and "price.vs_sector_1m_pct" in gaps
    nifty_1m = (float(NIFTY.iloc[-1]) / float(NIFTY.iloc[-22]) - 1) * 100
    assert p["vs_nifty_1m_pct"] == round(p["change_1m_pct"] - nifty_1m, 2)
    assert (pack["rules_verdict"] is None) == ("rules_verdict" in gaps)
    assert len(world) == 2                     # tried NSE results history and Google News once each; both "failed"


def test_pack_sections_are_point_in_time(world, monkeypatch):
    from app.engine.data import fetcher

    monkeypatch.setattr(fetcher, "fetch_fundamental_bundle", lambda s, **k: {
        "info": {"sector": "Technology", "industry": "Software"}, "quarterly": [], "cashflow": [], "ok": True})
    q = lambda key, period, filed, nature="Consolidated", rev=5.0e9: {  # noqa: E731
        "key": key, "symbol": "AAA", "period_end": period, "filed_on": filed, "nature": nature, "revenue": rev,
        "ebitda": 1.0e9, "net_profit": 6.5e8, "eps": 4.2, "margin_pct": 20.0}
    _store("results", [q("r1", "2026-09-30", "2026-10-30"), q("r2", "2026-09-30", "2026-10-30", "Standalone", 4.0e9),
                       q("r3", "2026-06-30", "2026-07-25", rev=4.5e9),
                       q("r4", "2026-12-31", "2026-11-20")])                       # filed after the day: not known yet
    _store("shareholding", [
        {"key": "p1", "symbol": "AAA", "kind": "pattern", "filed_on": "2026-10-20", "as_of": "2026-09-30",
         "promoter_pct": 41.5, "public_pct": 58.5, "pledge_pct": None},
        {"key": "p0", "symbol": "AAA", "kind": "pattern", "filed_on": "2026-07-20", "as_of": "2026-06-30",
         "promoter_pct": 40.0, "public_pct": 60.0, "pledge_pct": None},
        {"key": "g1", "symbol": "AAA", "kind": "pledge", "filed_on": "2026-10-25", "as_of": "2026-09-30",
         "promoter_pct": None, "public_pct": None, "pledge_pct": 3.25}])
    _store("deals", [{"key": "d1", "symbol": "AAA", "date": "2026-11-03", "kind": "bulk", "side": "buy",
                      "party": "Fund A", "qty": 120000, "price": 248.1},
                     {"key": "d0", "symbol": "AAA", "date": "2026-09-01", "kind": "block", "side": "sell",
                      "party": "Old Seller", "qty": 5, "price": 1.0}])                 # older than 30 days
    _store("insider", [])
    _store("announcements", [{"key": "a1", "symbol": "AAA", "date": "2026-11-04", "kind": "Press Release",
                              "title": "Order win"},
                             {"key": "a2", "symbol": "AAA", "date": "2026-11-12", "kind": "Upcoming: Board Meeting",
                              "title": "Results"}])
    _store("announcements", [{"key": "a3", "symbol": "AAA", "date": "2026-11-20", "kind": "Upcoming: AGM",
                              "title": "Pulled later"}], day=date(2026, 11, 10))
    _store("news", [{"key": "n1", "symbol": "AAA", "date": "2026-11-04", "title": "AAA wins order", "source": "ET",
                     "url": "https://x/n1"}])
    pack = _pack()
    assert [(r["period"], r["revenue"]) for r in pack["quarters"]] == [("2026-09-30", 500.0), ("2026-06-30", 450.0)]
    assert pack["quarters"][0] == {"period": "2026-09-30", "filed_on": "2026-10-30", "revenue": 500.0, "ebitda": 100.0,
                                   "net_profit": 65.0, "eps": 4.2, "margin_pct": 20.0}      # ₹ crore
    assert pack["ownership"] == {"as_of": "2026-09-30", "promoter_pct": 41.5, "promoter_change_pct": 1.5,
                                 "fii_pct": None, "dii_pct": None, "public_pct": 58.5, "pledge_pct": 3.25}
    assert pack["deals"] == [{"date": "2026-11-03", "kind": "bulk", "party": "Fund A", "qty": 120000, "price": 248.1}]
    assert [e["title"] for e in pack["events"]] == ["Results", "Order win"]                 # ahead first, then past
    assert [h["title"] for h in pack["headlines"]] == ["AAA wins order"]
    assert pack["market"]["sector_index"] == "NIFTY IT" and pack["market"]["sector_1w_pct"] is not None
    assert pack["price"]["vs_sector_1m_pct"] is not None
    gaps = set(pack["unavailable"])
    assert not gaps & {"quarters", "ownership", "deals", "deals.insider", "events", "headlines", "market.sector_index"}
    assert {"ownership.fii_pct", "ownership.dii_pct"} <= gaps
    assert len(world) == 1                 # two quarters stored (< 4): NSE history tried once; headlines were there


def test_evidence_endpoints(world, client):
    assert client.get("/api/v1/stocks/AAA/evidence").status_code == 404
    r = client.post("/api/v1/stocks/aaa/evidence")
    assert r.status_code == 201 and r.json()["symbol"] == "AAA" and r.json()["day"] == DAY
    got = client.get("/api/v1/stocks/AAA/evidence")
    assert got.status_code == 200 and got.json() == r.json()
    assert client.get("/api/v1/stocks/AAA/evidence", params={"day": DAY}).status_code == 200
    assert client.get("/api/v1/stocks/AAA/evidence", params={"day": "2026-11-04"}).status_code == 404
    assert client.get("/api/v1/stocks/AAA/evidence", params={"day": "5 Nov"}).status_code == 400
    assert client.post("/api/v1/stocks/NOPE/evidence").status_code == 404


def test_nightly_builds_the_brief_and_a_pack_per_followed_stock(world, client, monkeypatch):
    class Empty:
        def fetch(self, day, **kw):
            return []

    monkeypatch.setattr(nightly_brain, "MODULES", {s: Empty() for s in SOURCES})
    monkeypatch.setattr(market_brief_service.base_agent, "call_llm", lambda s, u: {"error": "no key"})
    client.post("/api/v1/pick-lists", json={"name": "Mine", "symbols": ["AAA", "ZZZ"]})
    job = nightly_brain.start_job(D)
    summary = nightly_brain.run(job.id, D)
    assert summary["brief"] == {"regime": "risk_on", "audited": False}
    assert summary["packs_built"] == 1 and list(summary["packs_failed"]) == ["ZZZ"]     # ZZZ did not trade
    brain = client.get("/api/v1/jobs/status").json()["brain"]
    assert brain["packs_built"] == 1 and client.get("/api/v1/stocks/AAA/evidence").status_code == 200
    assert client.get("/api/v1/market/brief").json()["regime"] == "risk_on"
