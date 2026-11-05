"""Step 7: Explore — the vectorised universe table must agree with scoring/market_metrics, plus search,
sort, paging and stock detail. Synthetic panel only.
"""
import numpy as np
import pandas as pd
import pytest

from app.engine.scoring.market_metrics import compute as compute_market_metrics
from app.services import explore_service, market_data

END = "2026-11-04"


def _panel():
    rng = np.random.default_rng(3)
    rows = []
    specs = {"TATAMOTORS": 300, "TATASTEEL": 270, "TATA": 40, "INFY": 10, "NEWLIST": 30, "BIGTATAX": 260, "OLDCO": 270}
    for sym, n in specs.items():
        dates = pd.bdate_range(end=END, periods=n)
        if sym == "OLDCO":
            dates = dates - pd.offsets.BDay(3)  # did not trade on END
        closes = 100 * np.cumprod(1 + rng.normal(0.001, 0.02, n))
        vols = rng.integers(1_000, 50_000, n)
        for d, c, v in zip(dates, closes, vols):
            rows.append({"symbol": sym, "date": d, "open": c, "high": c * 1.01, "low": c * 0.99, "close": c,
                         "volume": int(v), "turnover_lacs": c * v / 1e5, "deliv_qty": int(v) // 2, "deliv_pct": 50.0})
    return pd.DataFrame(rows).sort_values(["symbol", "date"]).reset_index(drop=True)


@pytest.fixture()
def explore(client, monkeypatch):
    monkeypatch.setattr(market_data, "_record_panel_day", lambda day: None)
    monkeypatch.setattr(explore_service, "_table", None)
    market_data.set_panel(_panel())


def test_table_matches_market_metrics(explore):
    day, df = explore_service.table()
    assert day == END and set(df["symbol"]) == {"TATAMOTORS", "TATASTEEL", "TATA", "INFY", "NEWLIST", "BIGTATAX"}
    for sym in df["symbol"]:
        row = df.set_index("symbol").loc[sym]
        hist = market_data.history(sym)
        m = compute_market_metrics(hist)
        for field, expected in (("change_1w_pct", m.change_1w_pct), ("change_1m_pct", m.change_1m_pct),
                                ("change_3m_pct", m.change_3m_pct), ("dist_from_52w_high_pct", m.dist_from_52w_high_pct),
                                ("volume_ratio_20d", m.volume_ratio_20d)):
            if expected is None:
                assert pd.isna(row[field]), (sym, field)
            else:
                assert row[field] == pytest.approx(expected, abs=0.01), (sym, field)
        c = hist["Close"]
        assert row["change_1d_pct"] == pytest.approx((c.iloc[-1] / c.iloc[-2] - 1) * 100, abs=0.01)
        if len(hist) >= 20:
            assert row["avg_turnover_lacs"] == pytest.approx(hist["TurnoverLacs"].tail(20).mean(), abs=0.01)
        else:
            assert pd.isna(row["avg_turnover_lacs"])  # fewer than 20 sessions: unavailable


def test_search_prefix_first_then_substring(client, explore):
    body = client.get("/api/v1/stocks?search=tata&sort=symbol&order=asc").json()
    assert body["trading_day"] == END and body["total"] == 4
    assert [i["symbol"] for i in body["items"]] == ["TATA", "TATAMOTORS", "TATASTEEL", "BIGTATAX"]


def test_sort_nulls_last_and_paging(client, explore):
    for order in ("asc", "desc"):
        items = client.get(f"/api/v1/stocks?sort=change_3m_pct&order={order}").json()["items"]
        values = [i["change_3m_pct"] for i in items]
        assert values[-3:] == [None, None, None]  # INFY, NEWLIST, TATA have < 64 sessions: no 3-month change
        known = values[:-3]
        assert known == sorted(known, reverse=(order == "desc"))
    page = client.get("/api/v1/stocks?sort=symbol&order=asc&limit=2&offset=2").json()
    assert page["total"] == 6 and [i["symbol"] for i in page["items"]] == ["NEWLIST", "TATA"]
    assert set(page["items"][0]) == {"symbol", "close", "change_1d_pct", "change_1w_pct", "change_1m_pct",
                                     "change_3m_pct", "dist_from_52w_high_pct", "volume_ratio_20d", "avg_turnover_lacs"}
    assert client.get("/api/v1/stocks?sort=colour").status_code == 400
    assert client.get("/api/v1/stocks?order=sideways").status_code == 400
    assert client.get("/api/v1/stocks?limit=0").status_code == 400


def test_stock_detail(client, explore):
    d = client.get("/api/v1/stocks/tatamotors").json()
    assert d["symbol"] == "TATAMOTORS" and d["trading_day"] == END
    assert d["metrics"]["symbol"] == "TATAMOTORS" and d["close"] == d["metrics"]["close"]
    assert d["indicators"]["ema200"] is not None and len(d["chart"]["dates"]) == 130
    short = client.get("/api/v1/stocks/INFY").json()
    assert short["indicators"]["rsi"] is None and short["metrics"]["change_1m_pct"] is None  # unavailable, not 0
    assert client.get("/api/v1/stocks/OLDCO").status_code == 404
    assert client.get("/api/v1/stocks/NOPE").status_code == 404


def test_search_with_no_match_is_empty_not_500(client, explore):
    body = client.get("/api/v1/stocks?search=zzzzqq").json()
    assert body == {"trading_day": END, "total": 0, "items": []}
    assert client.get("/api/v1/stocks?search=zzzzqq&sort=change_3m_pct&order=asc").json()["total"] == 0
