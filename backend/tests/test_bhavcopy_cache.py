"""Bhavcopy cache rules: a file only counts for the day it is dated, holidays are remembered, errors are retried.
NSE is faked; nothing here touches the network or the real cache directory.
"""
from datetime import date, timedelta

import pandas as pd
import pytest

from app.engine import config
from app.engine.data import nse_universe

HEADER = "SYMBOL, SERIES, DATE1, PREV_CLOSE, OPEN_PRICE, HIGH_PRICE, LOW_PRICE, LAST_PRICE, CLOSE_PRICE, AVG_PRICE, TTL_TRD_QNTY, TURNOVER_LACS, NO_OF_TRADES, DELIV_QTY, DELIV_PER"


def _csv(day: date, close: float = 100.0) -> str:
    d = day.strftime("%d-%b-%Y")
    return f"{HEADER}\nAAA, EQ, {d}, 99, 99, 101, 98, {close}, {close}, 100, 1000, 10.0, 50, 500, 50.0\n"


@pytest.fixture()
def fake_nse(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "BHAVCOPY_CACHE_DIR", str(tmp_path))
    calls: list[date] = []
    responses: dict[date, str | Exception] = {}

    def fake(day):
        calls.append(day)
        r = responses.get(day, "<!DOCTYPE html><html>no file</html>")
        if isinstance(r, Exception):
            raise r
        return r

    monkeypatch.setattr(nse_universe, "full_bhavcopy_raw", fake)
    return responses, calls, tmp_path


def test_previous_session_file_served_for_holiday_is_rejected(fake_nse):
    responses, calls, _ = fake_nse
    trading, holiday = date(2026, 10, 1), date(2026, 10, 2)
    responses[trading] = _csv(trading)
    responses[holiday] = _csv(trading)  # NSE hands back 01-Oct for 02-Oct
    assert nse_universe._fetch_day(trading) is not None
    assert nse_universe._fetch_day(holiday) is None
    assert nse_universe._fetch_day(holiday) is None
    assert calls.count(holiday) == 1  # remembered, not re-asked


def test_stale_cached_copy_is_ignored(fake_nse):
    _, calls, tmp = fake_nse
    sunday = date(2025, 8, 3)
    (tmp / "2025-08-03.csv").write_text("symbol,date,close\nAAA,2025-08-01,100\n")  # old buggy cache entry
    assert nse_universe._fetch_day(sunday) is None
    assert calls == []
    assert (tmp / "2025-08-03.csv").exists()  # left in place, just ignored


def test_html_page_marks_past_day_but_not_today(fake_nse):
    _, calls, _ = fake_nse
    past = date.today() - timedelta(days=3)
    assert nse_universe._fetch_day(past) is None
    assert nse_universe._fetch_day(past) is None
    assert calls.count(past) == 1
    today = date.today()
    nse_universe._fetch_day(today)
    nse_universe._fetch_day(today)
    assert calls.count(today) == 2  # today's file may be published later


def test_network_errors_are_retried(fake_nse):
    responses, calls, _ = fake_nse
    day = date(2026, 9, 2)
    responses[day] = ConnectionError("down")
    assert nse_universe._fetch_day(day) is None
    responses[day] = _csv(day)
    df = nse_universe._fetch_day(day)
    assert df is not None and df["date"].dt.date.tolist() == [day]
    assert calls.count(day) == 2


def test_dash_placeholders_become_missing_not_text(fake_nse):
    responses, _, _ = fake_nse
    today = date.today()
    good = _csv(today)
    dashed = good + f"BBB, EQ, {today.strftime('%d-%b-%Y')}, 99, 99, 101, 98, 100, 100, 100, 1000, 10.0, 50,  -,  -\n"
    responses[today] = dashed
    panel = nse_universe.build_market_panel(lookback_days=0)
    assert panel["deliv_pct"].dtype.kind == "f"
    assert panel.set_index("symbol").loc["BBB", "deliv_pct"] != panel.set_index("symbol").loc["BBB", "deliv_pct"]  # NaN
    assert panel.set_index("symbol").loc["AAA", "deliv_pct"] == 50.0


def test_panel_has_no_duplicate_symbol_days(fake_nse, monkeypatch):
    responses, _, _ = fake_nse
    today = date.today()
    for i in range(10):
        d = today - timedelta(days=i)
        responses[d] = _csv(today - timedelta(days=i - (i % 2)))  # every other day is a stale copy
    panel = nse_universe.build_market_panel(lookback_days=9)
    assert not panel.duplicated(["symbol", "date"]).any()
    assert pd.Series(panel["date"]).is_monotonic_increasing


def test_panel_for_any_range_downloads_once_and_caches(fake_nse):
    responses, calls, _ = fake_nse
    start, end = date(2024, 6, 10), date(2024, 6, 16)          # Mon..Sun, before NSE's July 2024 format change
    for d in (date(2024, 6, 10), date(2024, 6, 11), date(2024, 6, 12), date(2024, 6, 13), date(2024, 6, 14)):
        responses[d] = _csv(d)                                   # weekdays trade; the weekend gets the HTML page
    ticks = []
    panel = nse_universe.build_market_panel_range(start, end, progress=lambda done, total: ticks.append((done, total)))
    assert sorted(panel["date"].dt.date.unique()) == [date(2024, 6, d) for d in (10, 11, 12, 13, 14)]
    assert ticks[-1] == (7, 7) and len(ticks) == 7
    assert len(calls) == 7
    again = nse_universe.build_market_panel_range(start, end)
    assert len(calls) == 7 and again.equals(panel)               # everything (incl. the weekend) came from disk


def test_range_never_requests_future_days(fake_nse):
    _, calls, _ = fake_nse
    nse_universe.build_market_panel_range(date.today() - timedelta(days=1), date.today() + timedelta(days=30))
    assert max(calls) <= date.today()
    assert nse_universe.build_market_panel_range(date(2024, 1, 2), date(2024, 1, 1)).empty  # empty range


def test_live_panel_is_the_range_panel(fake_nse):
    responses, _, _ = fake_nse
    for i in range(5):
        d = date.today() - timedelta(days=i)
        responses[d] = _csv(d)
    live = nse_universe.build_market_panel(lookback_days=4)
    rng = nse_universe.build_market_panel_range(date.today() - timedelta(days=4), date.today())
    assert live.equals(rng) and len(live) == 5
