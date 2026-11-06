"""Brain source pullers (app/engine/data/sources) on recorded NSE / RSS fixtures: parsing, day filtering, live-only
endpoints refusing other days, never raising through pull(), cache rules, retries, and results with filing dates.
No network: every request is answered from tests/fixtures/sources.
"""
import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from app.engine.data.sources import (announcements, common, deals, global_cues, insider, market, news, results,
                                     shareholding)
from app.engine.data.sources.common import SourceUnavailable

FIX = Path(__file__).parent / "fixtures" / "sources"
DAY = date(2026, 11, 5)


class FakeResponse:
    def __init__(self, text):
        self.text = text

    def json(self):
        return json.loads(self.text)


ROUTES = {  # URL fragment -> fixture file
    "corporate-announcements": "nse_announcements.json", "event-calendar": "nse_event_calendar.json",
    "largedeal": "nse_largedeal.json", "corporates-pit": "nse_pit_constructed.json",
    "share-holdings-master": "nse_shareholding.json", "pledgedata": "nse_pledge.json",
    "fiidiiTradeReact": "nse_fiidii.json", "allIndices": "nse_allindices.json",
    "integrated-filing-results": "nse_integrated_results.json", "/corporate/xbrl/": "nse_mphasis_xbrl.xml",
    "1977021501": "rss_et_markets.xml", "2146842": "rss_et_stocks.xml", "news.google.com": "rss_google_mphasis.xml",
}


@pytest.fixture()
def nse(tmp_path, monkeypatch):
    """Serve every request from fixtures; `overrides` swaps a route's body; `calls` records URLs."""
    calls, overrides = [], {}
    monkeypatch.setattr(common, "CACHE_DIR", str(tmp_path / "sources"))

    def get(url, **kw):
        calls.append(url)
        for fragment, name in ROUTES.items():
            if fragment in url:
                body = overrides.get(fragment)
                if isinstance(body, Exception):
                    raise body
                return FakeResponse(body if body is not None else (FIX / name).read_text())
        raise SourceUnavailable(f"HTTP 404 from {url}")

    for session in (common.NSE, common.WEB):
        monkeypatch.setattr(session, "get", get)
    return {"calls": calls, "overrides": overrides}


# --- announcements -------------------------------------------------------------------------------------------

def test_announcements_for_the_day_plus_upcoming_events(nse):
    rows = announcements.fetch(DAY)
    anns = [r for r in rows if not r["kind"].startswith("Upcoming")]
    events = [r for r in rows if r["kind"].startswith("Upcoming")]
    assert anns and all(r["date"] == "2026-11-05" and r["symbol"] and r["key"].startswith("ann:") for r in anns)
    assert anns[0]["at"].startswith("2026-11-05T")
    assert events and events[0]["kind"] == "Upcoming: Financial Results"
    assert common.known_names()["mphasis limited"] == "MPHASIS"           # names remembered for pledges


# --- deals (live-only) ----------------------------------------------------------------------------------------

def test_deals_only_for_the_snapshot_day(nse):
    snapshot_day = common.parse_date(json.loads((FIX / "nse_largedeal.json").read_text())["as_on_date"])
    rows = deals.fetch(snapshot_day)
    assert rows and {r["kind"] for r in rows} <= {"bulk", "block"}
    assert all(r["date"] == snapshot_day.isoformat() and r["qty"] > 0 for r in rows)
    bulk = next(r for r in rows if r["kind"] == "bulk")
    assert bulk["side"] in ("BUY", "SELL") and bulk["party"] and bulk["price"]
    other = date(2026, 11, 3)
    with pytest.raises(SourceUnavailable, match="latest session only"):
        deals.fetch(other)
    assert deals.pull(other) == []                                            # pull never raises


# --- insider ---------------------------------------------------------------------------------------------------

def test_insider_rows_and_the_refused_endpoint(nse):
    rows = insider.fetch(DAY)
    assert len(rows) == 1 and rows[0]["symbol"] == "MPHASIS"                  # only disclosures dated the day
    assert (rows[0]["side"], rows[0]["qty"], rows[0]["price"]) == ("buy", 1200.0, 2880.0)
    nse["overrides"]["corporates-pit"] = json.dumps({"acqNameList": [], "data": []})
    with pytest.raises(SourceUnavailable, match="needs a browser session"):
        insider.fetch(date(2026, 11, 4))                                      # empty week = refused, not "none"


# --- shareholding -------------------------------------------------------------------------------------------------

def test_shareholding_patterns_and_pledges(nse):
    rows = shareholding.fetch_window(date(2026, 10, 1), DAY)
    patterns = [r for r in rows if r["kind"] == "pattern"]
    pledges = [r for r in rows if r["kind"] == "pledge"]
    assert patterns and all(r["promoter_pct"] is not None and r["filed_on"] <= "2026-11-05" for r in patterns)
    assert pledges and pledges[0]["symbol"] and pledges[0]["pledge_pct"] is not None  # matched by company name
    one_day = shareholding.fetch(DAY)
    assert all(r["filed_on"] == "2026-11-05" for r in one_day)


# --- market (live-only, close check) ---------------------------------------------------------------------------------

def test_market_flows_and_indices_only_at_the_close(nse):
    rows = market.fetch(DAY)                                                   # recorded allIndices is 06-Nov 14:49
    metrics = {r["key"]: r["value"] for r in rows if r["key"] != "_warning"}
    assert metrics["fii_net_cr"] is not None and metrics["dii_net_cr"] == -10444.54
    assert not any(k.startswith("index:") for k in metrics)
    assert any("not 2026-11-05" in r.get("note", "") for r in rows if r["key"] == "_warning")
    closing = json.loads((FIX / "nse_allindices.json").read_text())
    closing["timestamp"] = "05-Nov-2026 15:30"
    nse["overrides"]["allIndices"] = json.dumps(closing)
    rows = market.fetch(DAY, use_cache=False)
    metrics = {r["key"]: r["value"] for r in rows}
    assert metrics["index:NIFTY 50:close"] == 24868.2 and metrics["vix"] == 17.18
    assert metrics["index:NIFTY 50:pct_1w"] == round((24868.2 / 23053.1 - 1) * 100, 2)      # from oneWeekAgoVal
    assert metrics["index:NIFTY 50:pct_1m"] == round((24868.2 / 22776.1 - 1) * 100, 2)
    assert metrics["advances"] > 0 and metrics["advance_decline"] == round(metrics["advances"] / metrics["declines"], 3)
    closing["timestamp"] = "05-Nov-2026 14:00"
    nse["overrides"]["allIndices"] = json.dumps(closing)
    assert any("intraday" in r.get("note", "") for r in market.fetch(DAY, use_cache=False))


# --- global cues -----------------------------------------------------------------------------------------------------

def test_global_cues(monkeypatch):
    idx = pd.bdate_range(end="2026-11-05", periods=10)
    series = {"^GSPC": pd.Series(range(100, 110), index=idx, dtype=float)}

    def history(ticker, day):
        if ticker == "^TNX":
            raise ConnectionError("down")
        return series.get(ticker, pd.Series([80.0, 82.0], index=idx[-2:]))

    rows = global_cues._fetch(DAY, history=history)
    sp = next(r for r in rows if r["key"] == "global:sp500")
    assert (sp["value"], sp["change_1d_pct"], sp["change_1w_pct"]) == (109.0, round((109 / 108 - 1) * 100, 2),
                                                                         round((109 / 104 - 1) * 100, 2))
    assert any(r["key"] == "_warning" and "us10y" in r["note"] for r in rows)   # partial failure noted, not fatal


# --- news ---------------------------------------------------------------------------------------------------------------

def test_news_market_feeds_and_company_headlines(nse):
    day = date(2026, 11, 6)
    rows = [r for r in news.fetch(day, companies={"MPHASIS": "Mphasis"}) if r["key"] != "_warning"]
    market_items = [r for r in rows if r["symbol"] is None]
    company = [r for r in rows if r["symbol"] == "MPHASIS"]
    assert market_items and all(r["date"] == "2026-11-06" and r["source"] in ("ET Markets", "ET Stocks") for r in market_items)
    assert company and all(r["url"].startswith("http") and r["title"] for r in company)
    assert any("news.google.com" in c for c in nse["calls"])
    assert news.parse_rss((FIX / "rss_google_mphasis.xml").read_text(), "x")[0]["at"].endswith("+05:30")  # IST


# --- results (point in time) --------------------------------------------------------------------------------------------

def test_results_capture_filing_date_and_quarter_figures(nse):
    rows = results.fetch(DAY)
    assert rows and all(r["filed_on"] == "2026-11-05" and r["filed_at"].startswith("2026-11-05T") for r in rows)
    r = rows[0]
    assert (r["symbol"], r["period_end"], r["period_start"]) == ("MPHASIS", "2026-09-30", "2026-07-01")
    assert (r["revenue"], r["net_profit"], r["eps"]) == (45809300000.0, 5611260000.0, 29.39)  # quarter, not half-year
    assert r["ebitda"] == 7675710000 + 552130000 + 1536020000 - 1471680000
    assert r["margin_pct"] == round(r["ebitda"] / r["revenue"] * 100, 2) and r["parse_error"] is None
    assert results.parse_xbrl((FIX / "nse_mphasis_xbrl.xml").read_text(), "2026-06-30")["parse_error"]


def test_results_keep_the_filing_even_if_its_xbrl_fails(nse):
    nse["overrides"]["/corporate/xbrl/"] = SourceUnavailable("HTTP 503 from xbrl")
    rows = results.fetch(DAY)
    assert rows and rows[0]["filed_on"] == "2026-11-05" and rows[0]["revenue"] is None and rows[0]["parse_error"]


# --- cache, never-raise, plumbing ------------------------------------------------------------------------------------------

def test_cache_first_and_failures_never_cached(nse):
    announcements.fetch(DAY)
    n = len(nse["calls"])
    announcements.fetch(DAY)
    assert len(nse["calls"]) == n                                             # served from data/cache/sources
    assert Path(common.cache_path("announcements", DAY)).exists()
    with pytest.raises(SourceUnavailable):
        deals.fetch(date(2026, 11, 3))
    assert not Path(common.cache_path("deals", date(2026, 11, 3))).exists()   # a failure is retried next time
    nse["overrides"]["corporate-announcements"] = RuntimeError("boom")
    assert announcements.pull(date(2026, 11, 4)) == []                        # pull never raises


def test_parsers():
    assert common.num("1,22,500") == 122500.0 and common.num(" 48.20 ") == 48.2
    assert common.num("-") is None and common.num(None) is None and common.num("nil") is None
    assert common.parse_date("05-NOV-2026") == common.parse_date("05-Nov-2026 23:59:08") == DAY
    assert common.parse_date("2026-11-05") == DAY and common.parse_date("garbage") is None
    assert common.parse_datetime("05-Nov-2026 23:59:08") == "2026-11-05T23:59:08"


def test_throttled_session_retries_then_gives_up(monkeypatch):
    import requests

    sleeps = []
    monkeypatch.setattr(common, "_sleep", sleeps.append)
    s = common.ThrottledSession(min_interval=0.0)
    replies = iter([503, 503, 200])

    class R:
        def __init__(self, code):
            self.status_code, self.text = code, "{}"

    monkeypatch.setattr(s._session, "get", lambda url, **kw: R(next(replies)))
    assert s.get("https://x/api").status_code == 200 and sleeps == [2.0, 4.0]
    monkeypatch.setattr(s._session, "get", lambda url, **kw: R(404))
    with pytest.raises(SourceUnavailable, match="HTTP 404"):
        s.get("https://x/api")                                                # 4xx: no pointless retries
    monkeypatch.setattr(s._session, "get", lambda url, **kw: (_ for _ in ()).throw(requests.ConnectionError()))
    with pytest.raises(SourceUnavailable, match="ConnectionError"):
        s.get("https://x/api")
