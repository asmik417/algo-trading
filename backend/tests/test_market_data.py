"""Step 4: market_data service — panel caching per trading day, price lookups, NIFTY benchmark.
A synthetic panel replaces NSE; yfinance is faked. No network.
"""
import numpy as np
import pandas as pd
import pytest

from app.services import market_data


def synthetic_panel(symbols=("AAA", "BBB"), days=30, end="2026-11-04") -> pd.DataFrame:
    dates = pd.bdate_range(end=end, periods=days)
    rows = []
    for k, sym in enumerate(symbols):
        closes = 100 * (k + 1) + np.arange(days, dtype=float)
        for d, c in zip(dates, closes):
            rows.append({"symbol": sym, "date": d, "open": c - 1, "high": c + 1, "low": c - 2, "close": c,
                         "volume": 1000 + k, "turnover_lacs": 50.0, "deliv_qty": 500, "deliv_pct": 50.0})
    return pd.DataFrame(rows).sort_values(["symbol", "date"]).reset_index(drop=True)


@pytest.fixture(autouse=True)
def reset_market_data(monkeypatch):
    monkeypatch.setattr(market_data, "_panel", None)
    monkeypatch.setattr(market_data, "_panel_day", None)
    monkeypatch.setattr(market_data, "_histories", {})
    monkeypatch.setattr(market_data, "_latest_day", (None, 0.0))
    monkeypatch.setattr(market_data, "_nifty", {})
    monkeypatch.setattr(market_data, "_record_panel_day", lambda day: None)


def test_panel_built_once_per_trading_day(monkeypatch):
    builds = []
    day = {"value": "2026-11-03"}

    def build():
        builds.append(1)
        return synthetic_panel(end=day["value"])

    monkeypatch.setattr(market_data.nse_universe, "build_market_panel", build)
    monkeypatch.setattr(market_data, "latest_trading_day", lambda: day["value"])
    market_data.get_panel()
    market_data.get_panel()
    assert len(builds) == 1
    day["value"] = "2026-11-04"  # new bhavcopy published
    market_data.get_panel()
    assert len(builds) == 2
    assert market_data.known_trading_day() == "2026-11-04"


def test_history_and_closes():
    market_data.set_panel(synthetic_panel())
    h = market_data.history("AAA")
    assert list(h.columns) == ["Open", "High", "Low", "Close", "Volume", "DelivPct", "TurnoverLacs"]
    assert h.index.is_monotonic_increasing and len(h) == 30
    assert market_data.latest_close("AAA") == 129.0
    assert market_data.latest_close("BBB") == 229.0
    assert market_data.history("NOPE").empty
    assert market_data.latest_close("NOPE") is None


def test_close_on_uses_last_session_on_or_before():
    market_data.set_panel(synthetic_panel())
    assert market_data.close_on("AAA", "2026-11-04") == ("2026-11-04", 129.0)
    assert market_data.close_on("AAA", "2026-11-01") == ("2026-10-30", 126.0)  # Sunday -> Friday
    assert market_data.close_on("AAA", "2020-01-01") is None
    assert market_data.close_on("NOPE", "2026-11-04") is None


def test_nifty_change_pct(monkeypatch):
    idx = pd.bdate_range(end="2026-11-04", periods=5)
    closes = pd.Series([100.0, 101.0, 102.0, 103.0, 110.0], index=idx)
    monkeypatch.setattr(market_data, "_nifty_closes", lambda: closes)
    assert market_data.nifty_change_pct(idx[0].date()) == 10.0
    # Sunday 1 Nov -> Friday 30 Oct (close 101)
    assert market_data.nifty_change_pct("2026-11-01") == pytest.approx(round((110 / 101 - 1) * 100, 2))
    monkeypatch.setattr(market_data, "_nifty_closes", lambda: None)
    assert market_data.nifty_change_pct("2026-11-01") is None  # unavailable, never 0
