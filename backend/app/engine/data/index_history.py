"""Daily closes of NSE indices from yfinance, for days when NSE's own end-of-day index snapshot was not captured.
Only the indices Yahoo carries with full history are listed; anything else is simply unavailable.
"""
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pandas as pd

from app.core.logging import get_logger

log = get_logger(__name__)

# NSE index name -> Yahoo ticker (checked 2026-11-06: each returns a full daily history).
TICKERS = {
    "NIFTY 50": "^NSEI", "INDIA VIX": "^INDIAVIX", "NIFTY 100": "^CNX100", "NIFTY 500": "^CRSLDX",
    "NIFTY MIDCAP 50": "^NSEMDCP50", "NIFTY IT": "^CNXIT", "NIFTY BANK": "^NSEBANK", "NIFTY AUTO": "^CNXAUTO",
    "NIFTY FMCG": "^CNXFMCG", "NIFTY PHARMA": "^CNXPHARMA", "NIFTY METAL": "^CNXMETAL", "NIFTY REALTY": "^CNXREALTY",
    "NIFTY ENERGY": "^CNXENERGY", "NIFTY INFRASTRUCTURE": "^CNXINFRA", "NIFTY PSU BANK": "^CNXPSUBANK",
    "NIFTY FINANCIAL SERVICES": "NIFTY_FIN_SERVICE.NS", "NIFTY PSE": "^CNXPSE", "NIFTY INDIA CONSUMPTION": "^CNXCONSUM",
}

_lock = threading.Lock()
_cache: dict[tuple[str, str], pd.Series | None] = {}   # (calendar day fetched, index name) -> closes


def _download(ticker: str) -> pd.Series:
    import yfinance as yf

    hist = yf.Ticker(ticker).history(period="2y", interval="1d", auto_adjust=False)
    closes = hist["Close"].dropna() if not hist.empty else pd.Series(dtype=float)
    closes.index = pd.to_datetime(closes.index).tz_localize(None).normalize()
    return closes.astype(float)


def closes(name: str) -> pd.Series | None:
    """Daily closes for an NSE index (None when Yahoo does not carry it or the fetch failed). Fetched once a day."""
    ticker = TICKERS.get(name)
    if ticker is None:
        return None
    key = (date.today().isoformat(), name)
    with _lock:
        if key in _cache:
            return _cache[key]
    try:
        series = _download(ticker)
        series = series if not series.empty else None
    except Exception:
        log.warning("Index history for %s unavailable", name, exc_info=True)
        series = None
    with _lock:
        for stale in [k for k in _cache if k[0] != key[0]]:
            del _cache[stale]
        _cache[key] = series
    return series


def prefetch(names) -> None:
    """Fetch several indices at once (a cold day otherwise pays one Yahoo round trip per index in turn)."""
    todo = [n for n in names if n in TICKERS and (date.today().isoformat(), n) not in _cache]
    if todo:
        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(closes, todo))


def upto(series: pd.Series | None, day) -> pd.Series | None:
    """The closes on or before `day` (no look-ahead); None when nothing is left."""
    if series is None:
        return None
    out = series.loc[series.index <= pd.Timestamp(day)]
    return out if not out.empty else None


def change_pct(series: pd.Series | None, day, sessions: int) -> float | None:
    """% change of the close on/before `day` over the previous `sessions` sessions."""
    s = upto(series, day)
    if s is None or len(s) <= sessions or not s.iloc[-1 - sessions]:
        return None
    return round((float(s.iloc[-1]) / float(s.iloc[-1 - sessions]) - 1) * 100, 2)
