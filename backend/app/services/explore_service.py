"""Explore: the whole NSE universe as StockRows (one vectorised pass, cached per trading day), search/sort/page,
and a single stock's detail (metrics, indicators, chart). Metric definitions match scoring/market_metrics.py.
"""
import math
import threading

import pandas as pd

from app.services import analysis_service, market_data
from app.services.errors import BadInput, NotFound

NUMERIC_FIELDS = ["close", "change_1d_pct", "change_1w_pct", "change_1m_pct", "change_3m_pct",
                  "dist_from_52w_high_pct", "volume_ratio_20d", "avg_turnover_lacs"]
SORTABLE = ["symbol", *NUMERIC_FIELDS]
MAX_LIMIT = 500

_lock = threading.Lock()
_table: tuple[str, pd.DataFrame] | None = None   # (trading_day, one row per symbol)


def build_table(panel: pd.DataFrame, trading_day: str) -> pd.DataFrame:
    """One StockRow per symbol that traded on trading_day."""
    cols = ["symbol", "date", "close", "volume"] + (["turnover_lacs"] if "turnover_lacs" in panel else [])
    df = panel[cols].sort_values(["symbol", "date"]).reset_index(drop=True)
    g = df.groupby("symbol", sort=False)
    out = pd.DataFrame({"symbol": df["symbol"], "date": df["date"], "close": df["close"]})
    for rows, name in ((1, "change_1d_pct"), (5, "change_1w_pct"), (21, "change_1m_pct"), (63, "change_3m_pct")):
        out[name] = g["close"].pct_change(rows, fill_method=None) * 100
    high_252 = g["close"].rolling(252, min_periods=1).max().reset_index(level=0, drop=True)
    out["dist_from_52w_high_pct"] = (df["close"] - high_252) / high_252 * 100
    vol_20 = g["volume"].rolling(20, min_periods=20).mean().reset_index(level=0, drop=True)
    out["volume_ratio_20d"] = df["volume"] / vol_20.where(vol_20 > 0)
    if "turnover_lacs" in df:
        out["avg_turnover_lacs"] = g["turnover_lacs"].rolling(20, min_periods=20).mean().reset_index(level=0, drop=True)
    else:
        out["avg_turnover_lacs"] = float("nan")
    last = out[out["date"] == pd.Timestamp(trading_day)].drop(columns="date")
    return last.round({c: 2 for c in NUMERIC_FIELDS}).reset_index(drop=True)


def table() -> tuple[str, pd.DataFrame]:
    global _table
    day = market_data.panel_day()
    if not day:
        raise NotFound("Market data is not available yet.")
    with _lock:
        if _table is None or _table[0] != day:
            _table = (day, build_table(market_data.get_panel(), day))
        return _table


def _row(rec: dict) -> dict:
    return {k: (None if isinstance(v, float) and not math.isfinite(v) else v) for k, v in rec.items()}


def list_stocks(search: str = "", sort: str = "change_1m_pct", order: str = "desc", limit: int = 50,
                offset: int = 0) -> dict:
    if sort not in SORTABLE:
        raise BadInput(f"sort must be one of {', '.join(SORTABLE)}.")
    if order not in ("asc", "desc"):
        raise BadInput("order must be asc or desc.")
    limit, offset = max(1, min(int(limit), MAX_LIMIT)), max(0, int(offset))
    day, df = table()
    term = (search or "").strip().upper()
    if term:
        starts = df["symbol"].str.startswith(term)
        df = df[starts | df["symbol"].str.contains(term, regex=False)].assign(_match=(~starts).astype(int))
    else:
        df = df.assign(_match=0)
    # Prefix matches first, then substring matches; unavailable values always sort last.
    df = df.assign(_missing=df[sort].isna().astype(int))
    df = df.sort_values(["_match", "_missing", sort], ascending=[True, True, order == "asc"], kind="mergesort")
    page = df.iloc[offset: offset + limit].drop(columns=["_match", "_missing"])
    return {"trading_day": day, "total": len(df), "items": [_row(r) for r in page.to_dict("records")]}


def stock_detail(symbol: str) -> dict:
    sym = symbol.strip().upper()
    day, df = table()
    match = df[df["symbol"] == sym]
    if match.empty:
        raise NotFound(f"{sym} is not in the NSE universe for {day}.")
    metrics = _row(match.iloc[0].to_dict())
    hist = market_data.history(sym)
    return {"symbol": sym, "trading_day": day, "close": metrics["close"], "metrics": metrics,
            "indicators": analysis_service.indicators(hist), "chart": analysis_service.chart(hist)}
