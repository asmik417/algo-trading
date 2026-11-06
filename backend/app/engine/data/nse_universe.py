"""
Free, full-market NSE data via NSE's public bhavcopy archive (no API key,
no subscription — wrapped by the open-source `jugaad-data` library).

Each trading day's bhavcopy contains OHLCV + delivery % for every listed
security. Downloading and caching a rolling window of these gives us a full
price/volume/delivery history for the *entire* NSE equity universe without
making a single per-symbol API call — that's what powers the Stage 1
technical/volume prefilter for Emerging Opportunities across the whole
market, for free.
"""
import io
import os
from datetime import date, timedelta

import pandas as pd
from jugaad_data.nse import full_bhavcopy_raw

from app.engine import config
from app.engine.utils.logger import get_logger

log = get_logger(__name__)

_COLUMNS = {
    "SYMBOL": "symbol",
    " SERIES": "series",
    " DATE1": "date",
    " PREV_CLOSE": "prev_close",
    " OPEN_PRICE": "open",
    " HIGH_PRICE": "high",
    " LOW_PRICE": "low",
    " CLOSE_PRICE": "close",
    " TTL_TRD_QNTY": "volume",
    " TURNOVER_LACS": "turnover_lacs",
    " DELIV_QTY": "deliv_qty",
    " DELIV_PER": "deliv_pct",
}


def _cache_path(day: date) -> str:
    return os.path.join(config.BHAVCOPY_CACHE_DIR, f"{day.isoformat()}.csv")


def _no_trading_marker(day: date) -> str:
    return os.path.join(config.BHAVCOPY_CACHE_DIR, f"{day.isoformat()}.no-trading")


def _is_for_day(df: pd.DataFrame, day: date) -> bool:
    """NSE serves the *previous* session's file for some holidays and Sundays.
    A bhavcopy only counts for `day` if every row is dated `day`."""
    dates = pd.to_datetime(df["date"], errors="coerce").dt.date.unique()
    return len(dates) == 1 and dates[0] == day


def _mark_no_trading(day: date) -> None:
    # Only past days are final; today's file may simply not be published yet.
    if day < date.today():
        os.makedirs(config.BHAVCOPY_CACHE_DIR, exist_ok=True)
        open(_no_trading_marker(day), "w").close()


_downloads = 0


def _fetch_day(day: date) -> pd.DataFrame | None:
    """Return the equity-series (SERIES == EQ) bhavcopy for one day, or None
    if the day wasn't a trading day / data isn't published (weekend, holiday).
    Network errors are never cached; confirmed non-trading past days are."""
    global _downloads
    if os.path.exists(_no_trading_marker(day)):
        return None
    cache_path = _cache_path(day)
    if os.path.exists(cache_path):
        try:
            df = pd.read_csv(cache_path, parse_dates=["date"])
            if df.empty:
                return None
            if _is_for_day(df, day):
                return df
            _mark_no_trading(day)  # stale copy of an earlier session saved under this date
            return None
        except Exception:
            pass  # fall through and re-fetch a corrupt cache entry

    try:
        raw = full_bhavcopy_raw(day)
        df = pd.read_csv(io.StringIO(raw))
    except Exception:
        return None  # network / NSE error: try again next time

    _downloads += 1
    if _downloads % 10 == 0:
        log.info("Bhavcopy download progress: %d days fetched from NSE so far (at %s)", _downloads, day)

    df = df.rename(columns=_COLUMNS)
    if "series" not in df.columns or "symbol" not in df.columns:
        _mark_no_trading(day)  # NSE answered with its "no file" page
        return None

    # NSE's raw CSV pads every string cell with a leading space
    for col in ("symbol", "series", "date"):
        df[col] = df[col].astype(str).str.strip()

    df = df[df["series"] == "EQ"].copy()
    if df.empty:
        return None

    keep = ["symbol", "date", "open", "high", "low", "close", "volume", "turnover_lacs", "deliv_qty", "deliv_pct"]
    df = df[[c for c in keep if c in df.columns]]
    df["date"] = pd.to_datetime(df["date"], format="%d-%b-%Y", errors="coerce")
    df = df.dropna(subset=["date"])
    if df.empty or not _is_for_day(df, day):
        _mark_no_trading(day)
        return None

    os.makedirs(config.BHAVCOPY_CACHE_DIR, exist_ok=True)
    df.to_csv(cache_path, index=False)
    return df


def find_latest_trading_day(max_lookback_days: int = 10) -> date | None:
    """Cheapest possible way to know "what trading day is it" — walks back
    from today until a bhavcopy exists, without building the full panel.
    Each day checked is itself disk-cached, so repeat calls are near-instant."""
    day = date.today()
    for _ in range(max_lookback_days):
        if _fetch_day(day) is not None:
            return day
        day -= timedelta(days=1)
    return None


PANEL_COLUMNS = ["symbol", "date", "open", "high", "low", "close", "volume", "turnover_lacs", "deliv_pct"]


def _assemble(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Daily frames -> one clean long-format panel, sorted by symbol then date."""
    if not frames:
        return pd.DataFrame(columns=PANEL_COLUMNS)
    panel = pd.concat(frames, ignore_index=True)
    # NSE writes " -" for missing numbers (e.g. delivery on some fund rows); one such cell would turn a
    # whole column into text. Coerce to NaN = unavailable, never 0.
    for col in ("open", "high", "low", "close", "volume", "turnover_lacs", "deliv_qty", "deliv_pct"):
        if col in panel.columns:
            panel[col] = pd.to_numeric(panel[col], errors="coerce")
    panel = panel.dropna(subset=["close"])
    panel = panel.drop_duplicates(subset=["symbol", "date"], keep="last")
    return panel.sort_values(["symbol", "date"]).reset_index(drop=True)


def build_market_panel(lookback_days: int = config.BHAVCOPY_LOOKBACK_DAYS) -> pd.DataFrame:
    """Long-format DataFrame (symbol, date, open, high, low, close, volume,
    turnover_lacs, deliv_pct) covering every NSE equity for the last
    `lookback_days` calendar days. Cached to disk per trading day, so repeat
    calls only fetch the handful of days not already on disk."""
    today = date.today()
    panel = build_market_panel_range(today - timedelta(days=lookback_days), today)
    if panel.empty:
        log.error("Could not build any NSE market panel — bhavcopy fetch failed for every day in range")
    return panel


def build_market_panel_range(start: date, end: date, progress=None) -> pd.DataFrame:
    """The same panel for any calendar range [start, end] (e.g. years back, for backtests). Each day is read from
    the disk cache or downloaded once and cached, exactly like the live panel. `progress(done, total)` is called
    after every calendar day. Days after today are never requested."""
    end = min(end, date.today())
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)] if end >= start else []
    frames = []
    for i, day in enumerate(days, start=1):
        df = _fetch_day(day)
        if df is not None:
            frames.append(df)
        if progress is not None:
            progress(i, len(days))
    return _assemble(frames)


def latest_trading_day(panel: pd.DataFrame) -> pd.Timestamp | None:
    if panel.empty:
        return None
    return panel["date"].max()


def universe_symbols(panel: pd.DataFrame) -> list[str]:
    """All symbols present on the most recent trading day in the panel —
    i.e. the current tradeable NSE equity universe."""
    last_day = latest_trading_day(panel)
    if last_day is None:
        return []
    return sorted(panel.loc[panel["date"] == last_day, "symbol"].unique().tolist())


def symbol_price_history(panel: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """Per-symbol OHLCV history shaped like data.fetcher.fetch_price_history's
    output (DatetimeIndex, columns Open/High/Low/Close/Volume) so it's a
    drop-in for data.indicators.compute_indicators()."""
    sub = panel.loc[panel["symbol"] == symbol].sort_values("date")
    if sub.empty:
        return pd.DataFrame()
    cols = ["open", "high", "low", "close", "volume"]
    names = ["Open", "High", "Low", "Close", "Volume"]
    if "deliv_pct" in sub.columns:
        cols.append("deliv_pct")
        names.append("DelivPct")
    out = sub.set_index("date")[cols].copy()
    out.columns = names
    return out
