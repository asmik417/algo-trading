import threading
import time

import pandas as pd
import yfinance as yf
from yfinance.exceptions import YFRateLimitError

from app.engine.utils.logger import get_logger

log = get_logger(__name__)


def get_nse_symbol(symbol: str) -> str:
    symbol = symbol.upper().strip()
    if not symbol.endswith(".NS") and not symbol.endswith(".BO"):
        return f"{symbol}.NS"
    return symbol


def fetch_price_history(symbol: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame | None:
    nse_sym = get_nse_symbol(symbol)
    try:
        ticker = yf.Ticker(nse_sym)
        df = ticker.history(period=period, interval=interval)
        if df.empty:
            log.warning(f"No data returned for {nse_sym}")
            return None
        df.index = pd.to_datetime(df.index)
        return df
    except Exception as e:
        log.error(f"Failed to fetch history for {nse_sym}: {e}")
        return None


def fetch_fundamentals(symbol: str) -> dict:
    nse_sym = get_nse_symbol(symbol)
    result = {
        "symbol": symbol,
        "pe_ratio": None,
        "pb_ratio": None,
        "eps": None,
        "market_cap": None,
        "revenue_growth": None,
        "profit_margins": None,
        "debt_to_equity": None,
        "roe": None,
        "sector": None,
        "industry": None,
        "52w_high": None,
        "52w_low": None,
        "current_price": None,
        "analyst_target": None,
    }
    try:
        ticker = yf.Ticker(nse_sym)
        info = ticker.info

        result["pe_ratio"] = info.get("trailingPE")
        result["pb_ratio"] = info.get("priceToBook")
        result["eps"] = info.get("trailingEps")
        result["market_cap"] = info.get("marketCap")
        result["revenue_growth"] = info.get("revenueGrowth")
        result["profit_margins"] = info.get("profitMargins")
        result["debt_to_equity"] = info.get("debtToEquity")
        result["roe"] = info.get("returnOnEquity")
        result["sector"] = info.get("sector")
        result["industry"] = info.get("industry")
        result["52w_high"] = info.get("fiftyTwoWeekHigh")
        result["52w_low"] = info.get("fiftyTwoWeekLow")
        result["current_price"] = info.get("currentPrice") or info.get("regularMarketPrice")
        result["analyst_target"] = info.get("targetMeanPrice")
    except Exception as e:
        log.warning(f"Could not fetch fundamentals for {nse_sym}: {e}")

    return result


def fetch_quarterly_financials(symbol: str) -> list[dict]:
    """Chronologically ascending list of {"period", "revenue", "net_income",
    "eps"} (most recent quarter last). yfinance typically returns 4-5
    quarters for NSE names — enough for one YoY comparison, sometimes two."""
    nse_sym = get_nse_symbol(symbol)
    try:
        return _parse_quarterly(yf.Ticker(nse_sym).quarterly_financials)
    except Exception as e:
        log.warning(f"Could not fetch quarterly financials for {nse_sym}: {e}")
        return []


def _parse_quarterly(qf) -> list[dict]:
    out = []
    if qf is None or qf.empty:
        return out
    for period in sorted(qf.columns, reverse=False):  # oldest -> newest
        col = qf[period]
        out.append({
            "period": str(period.date()) if hasattr(period, "date") else str(period),
            "revenue": _safe_row(col, "Total Revenue"),
            "net_income": _safe_row(col, "Net Income"),
            "eps": _safe_row(col, "Diluted EPS") or _safe_row(col, "Basic EPS"),
        })
    return out


def fetch_cashflow_trend(symbol: str) -> list[dict]:
    """Chronologically ascending list of {"period", "fcf", "ocf"} from annual
    cash-flow statements (most recent year last)."""
    nse_sym = get_nse_symbol(symbol)
    try:
        return _parse_cashflow(yf.Ticker(nse_sym).cashflow)
    except Exception as e:
        log.warning(f"Could not fetch cashflow trend for {nse_sym}: {e}")
        return []


def _parse_cashflow(cf) -> list[dict]:
    out = []
    if cf is None or cf.empty:
        return out
    for period in sorted(cf.columns, reverse=False):
        col = cf[period]
        out.append({
            "period": str(period.date()) if hasattr(period, "date") else str(period),
            "fcf": _safe_row(col, "Free Cash Flow"),
            "ocf": _safe_row(col, "Operating Cash Flow"),
        })
    return out


class RateLimiter:
    """Spaces out request starts across threads (min_interval seconds apart). Shared cooldown: once Yahoo
    rate-limits any request, every fetch waits until the cooldown has passed."""

    def __init__(self, min_interval: float):
        self.min_interval = min_interval
        self._next = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            start = max(now, self._next, _cooldown_until)
            self._next = start + self.min_interval
        if start > now:
            _sleep(start - now)


# Bulk fetches (backtests, cache repair): about 2 bundles a second, ~6 Yahoo requests a second.
BULK_LIMITER = RateLimiter(min_interval=0.5)
RATE_LIMIT_COOLDOWN_S = 30.0
RETRIES = 3
BACKOFF_S = 2.0
_cooldown_until = 0.0
_sleep = time.sleep  # replaced in tests


def is_rate_limit(exc: BaseException) -> bool:
    if isinstance(exc, YFRateLimitError):
        return True
    text = str(exc)
    return any(marker in text for marker in ("Too Many Requests", "Rate limited", "429"))


def _start_cooldown() -> None:
    global _cooldown_until
    _cooldown_until = max(_cooldown_until, time.monotonic() + RATE_LIMIT_COOLDOWN_S)


def _fetch_once(nse_sym: str) -> tuple[dict, Exception | None]:
    """One attempt. `info` first: if it fails nothing else is trusted, because yfinance answers the quarterly and
    cash-flow calls with silently empty tables when it is rate-limited."""
    bundle = {"info": {}, "quarterly": [], "cashflow": []}
    ticker = yf.Ticker(nse_sym)
    try:
        bundle["info"] = dict(ticker.info or {})
    except Exception as e:
        return bundle, e
    if not bundle["info"]:
        return bundle, None  # Yahoo has nothing for this symbol: genuinely empty, not an error
    for key, load in (("quarterly", lambda: _parse_quarterly(ticker.quarterly_financials)),
                      ("cashflow", lambda: _parse_cashflow(ticker.cashflow))):
        try:
            bundle[key] = load()
        except Exception as e:
            log.warning(f"Could not fetch {key} for {nse_sym}: {e}")
    return bundle, None


def fetch_fundamental_bundle(symbol: str, limiter: RateLimiter | None = None, retries: int = RETRIES) -> dict:
    """Everything the scoring engine needs from yfinance, via one Ticker:
    {"info": raw yfinance info (trailingPE, returnOnEquity, marketCap, ...),
     "quarterly": fetch_quarterly_financials shape, "cashflow": fetch_cashflow_trend shape,
     "ok": True only when `info` came back, "rate_limited": the last failure was a Yahoo rate limit}.
    A failed attempt is retried up to `retries` times with exponential backoff; a rate limit also starts a shared
    cooldown. A symbol Yahoo simply has no data for is not retried. The pillars read raw yfinance keys."""
    nse_sym = get_nse_symbol(symbol)
    error: Exception | None = None
    for attempt in range(retries + 1):
        if limiter is not None:
            limiter.wait()
        elif _cooldown_until > time.monotonic():
            _sleep(_cooldown_until - time.monotonic())
        bundle, error = _fetch_once(nse_sym)
        if error is None:
            return {**bundle, "ok": bool(bundle["info"]), "rate_limited": False}
        limited = is_rate_limit(error)
        if limited:
            _start_cooldown()
        log.warning(f"Could not fetch info for {nse_sym} (attempt {attempt + 1} of {retries + 1}"
                    f"{', rate-limited' if limited else ''}): {error}")
        if attempt < retries:
            _sleep(BACKOFF_S * 2 ** attempt)
    return {"info": {}, "quarterly": [], "cashflow": [], "ok": False, "rate_limited": is_rate_limit(error)}


def _safe_row(col, row_name: str) -> float | None:
    try:
        val = col.get(row_name)
    except Exception:
        return None
    if val is None or pd.isna(val):
        return None
    return float(val)


def fetch_news(symbol: str, limit: int = 5) -> list[dict]:
    nse_sym = get_nse_symbol(symbol)
    try:
        ticker = yf.Ticker(nse_sym)
        news = ticker.news or []
        out = []
        for item in news[:limit]:
            content = item.get("content", {})
            out.append({
                "title": content.get("title", ""),
                "summary": content.get("summary", ""),
                "publisher": content.get("provider", {}).get("displayName", ""),
            })
        return out
    except Exception as e:
        log.warning(f"Could not fetch news for {nse_sym}: {e}")
        return []
