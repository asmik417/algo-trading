"""Step 6 end-to-end: run the algo for a profile over a tiny synthetic market, then read runs, suggestions,
the dialog detail and ad-hoc Explore analysis through the API. No network: panel and yfinance are faked.
"""
import numpy as np
import pandas as pd
import pytest

from app.engine import config as engine_config
from app.services import market_data, run_registry, suggestion_service

END = "2026-11-04"
N = 160


def _rows(sym, closes, volumes):
    dates = pd.bdate_range(end=END, periods=len(closes))
    return [{"symbol": sym, "date": d, "open": c * 0.995, "high": c * 1.01, "low": c * 0.99, "close": c,
             "volume": v, "turnover_lacs": c * v / 1e5, "deliv_qty": v // 2, "deliv_pct": 55.0}
            for d, c, v in zip(dates, closes, volumes)]


def _breakout(base):
    rng = np.random.default_rng(7)
    flat = base * (1 + rng.uniform(-0.03, 0.03, N - 10))
    run_up = base * np.array([1.03, 1.05, 1.07, 1.09, 1.10, 1.11, 1.12, 1.13, 1.135, 1.14])
    vols = [100_000] * (N - 10) + [300_000] * 10
    return list(flat) + list(run_up), vols


def synthetic_market() -> pd.DataFrame:
    rows = []
    for sym in ("GOODCO", "ETFCO", "PRICEYCO", "OLDNEWS"):
        closes, vols = _breakout(500.0)
        rows += _rows(sym, closes, vols)
    closes, vols = _breakout(2.0)
    rows += _rows("PENNYCO", closes, vols)
    rows += _rows("DELISTED", [100.0] * 80, [10_000] * 80)[:-5]  # stopped trading before END
    return pd.DataFrame(rows).sort_values(["symbol", "date"]).reset_index(drop=True)


STRONG_INFO = {"trailingPE": 22.0, "priceToBook": 4.0, "returnOnEquity": 0.22, "operatingMargins": 0.18,
               "profitMargins": 0.12, "debtToEquity": 25.0, "marketCap": 3e11, "sector": "Technology",
               "industry": "Software"}
QUARTERLY = [{"period": f"Q{i}", "revenue": r, "net_income": ni, "eps": ni / 1e8}
             for i, (r, ni) in enumerate(zip([100, 105, 112, 120, 130], [10, 11, 13, 12, 30]))]
CASHFLOW = [{"period": "FY25", "fcf": 5e9, "ocf": 6e9}]
BUNDLES = {
    "GOODCO": {"info": STRONG_INFO, "quarterly": QUARTERLY, "cashflow": CASHFLOW, "ok": True},
    "PRICEYCO": {"info": {**STRONG_INFO, "trailingPE": 95.0}, "quarterly": QUARTERLY, "cashflow": CASHFLOW, "ok": True},
    "OLDNEWS": {"info": {**STRONG_INFO, "returnOnEquity": 0.05}, "quarterly": QUARTERLY, "cashflow": CASHFLOW, "ok": True},
    "ETFCO": {"info": {}, "quarterly": [], "cashflow": [], "ok": True},
}
OPEN_PARAMS = {"rsi_max": 100.0, "max_3m_runup_pct": 500.0, "min_volume_ratio": 0.0, "min_score": 30.0}


@pytest.fixture()
def market(client, tmp_path, monkeypatch):
    fetches: list[str] = []

    def fake_bundle(sym, **kw):
        fetches.append(sym)
        return BUNDLES.get(sym, {"info": {}, "quarterly": [], "cashflow": [], "ok": False})

    monkeypatch.setattr(engine_config, "FUNDAMENTALS_CACHE_DIR", str(tmp_path / "fundamentals"))
    monkeypatch.setattr(engine_config, "ANTHROPIC_API_KEY", "")  # deterministic narration
    monkeypatch.setattr(suggestion_service.fetcher, "fetch_fundamental_bundle", fake_bundle)
    monkeypatch.setattr(suggestion_service, "_spawn", lambda run_id, force: suggestion_service.execute_run(run_id, force))
    monkeypatch.setattr(market_data, "_record_panel_day", lambda day: None)
    suggestion_service._stage1_cache.clear()
    run_registry.clear()
    market_data.set_panel(synthetic_market())
    yield fetches
    run_registry.clear()


def _profile(client, **params) -> int:
    r = client.post("/api/v1/profiles", json={"name": f"Test {len(params)} {sorted(params)}", "owner": "T",
                                              "params": {**OPEN_PARAMS, **params}})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _run(client, pid, **body) -> dict:
    r = client.post(f"/api/v1/profiles/{pid}/runs", json=body or None)
    assert r.status_code == 202, r.text
    return client.get(f"/api/v1/runs/{r.json()['id']}").json()


def test_run_end_to_end(client, market):
    pid = _profile(client)
    run = _run(client, pid)
    assert run["status"] == "done", run["error"]
    assert run["trading_day"] == END
    assert run["progress"]["phase"] == "done"
    assert run["universe_size"] == 5            # DELISTED did not trade on END
    assert run["scored_size"] == 3              # ETFCO skipped (no fundamentals); PENNYCO prefiltered (price < 5)
    assert run["passed_size"] == 1              # PRICEYCO fails P/E, OLDNEWS fails ROE
    assert "PENNYCO" not in market and "DELISTED" not in market

    body = client.get(f"/api/v1/profiles/{pid}/suggestions").json()
    assert body["run"]["id"] == run["id"]
    [item] = body["items"]
    assert (item["symbol"], item["rank"], item["source"]) == ("GOODCO", 1, "run")
    assert item["market_cap_bucket"] == "Large Cap" and item["sector"] == "Technology"
    assert item["stop_loss"] < item["entry_optimal"] <= item["price"] < item["target"]
    assert item["is_tracked"] is False and item["position_id"] is None
    assert item["signal"] != "🔴 Weak / Invalidated"


def test_detail_has_everything_the_dialog_needs(client, market):
    pid = _profile(client)
    _run(client, pid)
    sid = client.get(f"/api/v1/profiles/{pid}/suggestions").json()["items"][0]["id"]
    d = client.get(f"/api/v1/suggestions/{sid}").json()
    # 160 synthetic sessions are too few for a 200-day EMA, so that (now default) filter is reported as skipped.
    assert d["trading_day"] == END and d["filters"] == {"passed": True, "failures": ["200-day EMA unavailable, filter skipped"]}
    assert d["reasons"]["why_flagged"].startswith("GOODCO was flagged")
    assert d["plan"]["disclaimer"].startswith("This plan is rules-based")
    assert d["plan"]["exit_note"].startswith("Book profit at ₹")
    keys = [p["key"] for p in d["score_breakdown"]]
    assert keys == ["earnings_acceleration", "fundamental_quality", "early_price_position",
                    "volume_accumulation", "technical_setup", "valuation"]
    for p in d["score_breakdown"]:
        assert p["max"] == p["weight"]
        assert p["score"] is None or 0 <= p["score"] <= p["max"]
    available = [p for p in d["score_breakdown"] if p["available"]]
    assert sum(p["score"] for p in available) / sum(p["weight"] for p in available) * 100 == pytest.approx(d["score"], abs=0.2)
    f = d["fundamentals"]
    assert (f["pe"], f["roe_pct"], f["market_cap"], f["operating_margin_pct"]) == (22.0, 22.0, 3e11, 18.0)
    assert f["latest_ocf"] == 6e9
    assert len(d["chart"]["dates"]) == 130 and d["chart"]["ema50"][-1] is not None
    assert d["indicators"]["rsi"] is not None
    # narration is cached after the first request
    assert client.get(f"/api/v1/suggestions/{sid}").json()["reasons"] == d["reasons"]


def test_rerun_with_new_weights_rescores_from_cache(client, market):
    pid = _profile(client)
    _run(client, pid)
    fetched = len(market)
    client.put(f"/api/v1/profiles/{pid}", json={"params": {
        "w_earnings_acceleration": 10, "w_fundamental_quality": 10, "w_early_price_position": 10,
        "w_volume_accumulation": 10, "w_technical_setup": 50, "w_valuation": 10}})
    run2 = _run(client, pid)
    assert run2["status"] == "done"
    # Stocks with fundamentals come from the cache; ETFCO's bundle has no info, so it is never cached and is
    # simply asked for again (an empty answer may be a rate limit, not the truth).
    assert market[fetched:] == ["ETFCO"]
    _run(client, pid, force_refetch=True)
    assert len(market) > fetched


def test_filters_change_with_params(client, market):
    pid = _profile(client, max_pe=0.0, min_roe_pct=0.0)  # P/E filter off, ROE floor off
    run = _run(client, pid)
    assert run["passed_size"] == 3
    symbols = [i["symbol"] for i in client.get(f"/api/v1/profiles/{pid}/suggestions").json()["items"]]
    assert set(symbols) == {"GOODCO", "PRICEYCO", "OLDNEWS"}
    assert [i["rank"] for i in client.get(f"/api/v1/profiles/{pid}/suggestions").json()["items"]] == [1, 2, 3]


def test_no_runs_yet_and_bad_run_refs(client, market):
    pid = _profile(client)
    assert client.get(f"/api/v1/profiles/{pid}/suggestions").json() == {"run": None, "items": []}
    assert client.get(f"/api/v1/profiles/{pid}/suggestions?run_id=999").status_code == 404
    assert client.get(f"/api/v1/profiles/{pid}/suggestions?run_id=abc").status_code == 400
    assert client.get("/api/v1/runs/999").status_code == 404
    assert client.post("/api/v1/profiles/999/runs").status_code == 404


def test_active_run_is_returned_not_duplicated(client, market, monkeypatch):
    monkeypatch.setattr(suggestion_service, "_spawn", lambda run_id, force: None)  # leave it queued
    pid = _profile(client)
    first = client.post(f"/api/v1/profiles/{pid}/runs")
    assert first.status_code == 202 and first.json()["status"] == "queued"
    second = client.post(f"/api/v1/profiles/{pid}/runs")
    assert second.status_code == 200 and second.json()["id"] == first.json()["id"]
    runs = client.get(f"/api/v1/profiles/{pid}/runs").json()
    assert [r["id"] for r in runs] == [first.json()["id"]]


def test_failed_run_records_error(client, market, monkeypatch):
    pid = _profile(client)

    def boom(*a, **k):
        raise RuntimeError("panel exploded")

    monkeypatch.setattr(suggestion_service, "prefilter", boom)
    run = _run(client, pid)
    assert run["status"] == "failed" and "panel exploded" in run["error"] and run["finished_at"]
    assert run_registry.active_run(pid) is None  # a new run can start


def test_analyze_persists_explore_suggestion(client, market):
    pid = _profile(client)
    r = client.post(f"/api/v1/stocks/priceyco/analyze?profile_id={pid}")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["source"] == "explore" and isinstance(d["id"], int) and d["rank"] is None
    assert d["filters"] == {"passed": False, "failures": ["P/E 95 above max 50"]}
    assert client.get(f"/api/v1/suggestions/{d['id']}").json()["symbol"] == "PRICEYCO"
    assert client.get(f"/api/v1/profiles/{pid}/suggestions").json()["items"] == []  # explore rows never listed

    etf = client.post(f"/api/v1/stocks/ETFCO/analyze?profile_id={pid}").json()
    assert etf["filters"]["failures"][0] == suggestion_service.NO_FUNDAMENTALS

    assert client.post(f"/api/v1/stocks/NOPE/analyze?profile_id={pid}").status_code == 404
    assert client.post(f"/api/v1/stocks/DELISTED/analyze?profile_id={pid}").status_code == 404
    assert client.post("/api/v1/stocks/GOODCO/analyze?profile_id=999").status_code == 404


def test_interrupted_runs_are_failed_on_startup(client, market, monkeypatch):
    from app.db.session import SessionLocal

    monkeypatch.setattr(suggestion_service, "_spawn", lambda run_id, force: None)
    pid = _profile(client)
    rid = client.post(f"/api/v1/profiles/{pid}/runs").json()["id"]
    run_registry.clear()  # simulate a restart: the in-memory registry is gone
    with SessionLocal() as db:
        suggestion_service.recover_interrupted_runs(db)
    run = client.get(f"/api/v1/runs/{rid}").json()
    assert run["status"] == "failed" and "restarted" in run["error"]


def test_narration_cache_rules(client, market, monkeypatch):
    from app.engine.agents import emerging_explainer
    from app.services import analysis_service

    pid = _profile(client)
    _run(client, pid)
    sid = client.get(f"/api/v1/profiles/{pid}/suggestions").json()["items"][0]["id"]
    calls = []
    llm = {"answer": None}  # None = LLM failing (e.g. no credits)
    monkeypatch.setattr(engine_config, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(emerging_explainer, "call_llm_explain", lambda c: calls.append(c.symbol) or llm["answer"])

    first = client.get(f"/api/v1/suggestions/{sid}").json()["reasons"]
    assert first["why_flagged"].startswith("GOODCO was flagged as") and "Net profit grew" in first["why_flagged"]
    assert first["what_changed"].startswith("Latest quarter profit grew") and first["what_changed"] != first["why_flagged"]
    client.get(f"/api/v1/suggestions/{sid}")
    assert len(calls) == 1  # fallback cached, LLM not hammered

    llm["answer"] = {"why_flagged": "LLM says why.", "what_changed": "LLM says what."}
    monkeypatch.setattr(analysis_service, "FALLBACK_RETRY_S", 0)  # retry window passed
    assert client.get(f"/api/v1/suggestions/{sid}").json()["reasons"]["why_flagged"] == "LLM says why."
    client.get(f"/api/v1/suggestions/{sid}")
    assert len(calls) == 2  # real narration is cached for good


def test_skipped_filters_listed_only_when_passed(client, market, monkeypatch):
    no_roe = {k: v for k, v in STRONG_INFO.items() if k != "returnOnEquity"}
    monkeypatch.setitem(BUNDLES, "GOODCO", {**BUNDLES["GOODCO"], "info": no_roe})
    monkeypatch.setitem(BUNDLES, "PRICEYCO", {**BUNDLES["PRICEYCO"], "info": {**no_roe, "trailingPE": 95.0}})
    pid = _profile(client)
    good = client.post(f"/api/v1/stocks/GOODCO/analyze?profile_id={pid}").json()
    assert good["filters"] == {"passed": True, "failures": ["ROE unavailable, filter skipped",
                                                           "200-day EMA unavailable, filter skipped"]}
    pricey = client.post(f"/api/v1/stocks/PRICEYCO/analyze?profile_id={pid}").json()
    assert pricey["filters"] == {"passed": False, "failures": ["P/E 95 above max 50"]}  # real failures only


def test_corporate_action_excluded_from_runs_and_analyze(client, market, monkeypatch):
    closes, vols = _breakout(500.0)
    closes = closes[:-40] + [c / 5 for c in closes[-40:]]  # 1:5 split 40 sessions ago
    split_day = pd.bdate_range(end=END, periods=N)[-40].date().isoformat()
    market_data.set_panel(pd.concat([synthetic_market(), pd.DataFrame(_rows("SPLITCO", closes, vols))])
                          .sort_values(["symbol", "date"]).reset_index(drop=True))
    monkeypatch.setitem(BUNDLES, "SPLITCO", BUNDLES["GOODCO"])
    pid = _profile(client)
    run = _run(client, pid)
    assert run["status"] == "done" and "SPLITCO" in market  # scored, then excluded
    assert [i["symbol"] for i in client.get(f"/api/v1/profiles/{pid}/suggestions").json()["items"]] == ["GOODCO"]
    d = client.post(f"/api/v1/stocks/SPLITCO/analyze?profile_id={pid}").json()
    assert d["filters"]["passed"] is False
    assert d["filters"]["failures"][0] == f"Possible corporate action on {split_day}, excluded"
    good = client.post(f"/api/v1/stocks/GOODCO/analyze?profile_id={pid}").json()
    assert not any("corporate action" in f for f in good["filters"]["failures"])


def test_corporate_action_window_is_130_sessions():
    idx = pd.bdate_range(end=END, periods=200)
    old = pd.DataFrame({"Close": [100.0] * 60 + [50.0] * 140}, index=idx)      # gap 140 sessions ago
    recent = pd.DataFrame({"Close": [100.0] * 80 + [50.0] * 120}, index=idx)   # gap 120 sessions ago
    assert suggestion_service.corporate_action_date(old) is None
    assert suggestion_service.corporate_action_date(recent) == idx[80].date().isoformat()
