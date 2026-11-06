"""Market data for the whole app: the NSE bhavcopy panel (cached in memory per trading day) and price lookups.
Also the NIFTY 50 benchmark change via yfinance. Every lookup returns None when data is missing, never 0.
"""
import os
import threading
import time
from datetime import date, timedelta

import pandas as pd

from app.core.logging import get_logger
from app.engine import config as engine_config
from app.engine.data import nse_universe

log = get_logger(__name__)

_LATEST_DAY_TTL_S = 600  # re-ask NSE "which day is it" at most every 10 minutes

_lock = threading.RLock()
_panel: pd.DataFrame | None = None
_panel_day: str | None = None
_histories: dict[str, pd.DataFrame] = {}
_latest_day: tuple[str | None, float] = (None, 0.0)
_nifty: dict[str, pd.Series | None] = {}  # calendar day -> NIFTY close series (or None on failure)
_building = threading.Event()


# --- trading day -------------------------------------------------------------

def latest_trading_day() -> str | None:
    """Most recent day NSE has published a bhavcopy for (ISO). Memoised for 10 minutes."""
    global _latest_day
    value, checked = _latest_day
    if value is not None and time.monotonic() - checked < _LATEST_DAY_TTL_S:
        return value
    day = nse_universe.find_latest_trading_day()
    value = day.isoformat() if day else (_panel_day or value)
    _latest_day = (value, time.monotonic())
    return value


def known_trading_day() -> str | None:
    """Offline answer for /health: the panel's day if built, else the newest valid file on disk."""
    if _panel_day:
        return _panel_day
    try:
        names = sorted((f for f in os.listdir(engine_config.BHAVCOPY_CACHE_DIR) if f.endswith(".csv")), reverse=True)
    except FileNotFoundError:
        return None
    for name in names[:15]:
        marker = os.path.join(engine_config.BHAVCOPY_CACHE_DIR, name[:-4] + ".no-trading")
        if os.path.exists(marker):
            continue
        try:
            first = pd.read_csv(os.path.join(engine_config.BHAVCOPY_CACHE_DIR, name), usecols=["date"], nrows=1)
            if str(first["date"].iloc[0])[:10] == name[:-4]:
                return name[:-4]
        except Exception:
            continue
    return None


def is_building() -> bool:
    return _building.is_set()


def refresh() -> str | None:
    """Forget the memoised trading day, re-check NSE, and rebuild the panel if a new day was published."""
    global _latest_day
    _latest_day = (None, 0.0)
    get_panel()
    return _panel_day


def panel_day() -> str | None:
    """Trading day of the current panel (builds it if needed)."""
    get_panel()
    return _panel_day


# --- panel -------------------------------------------------------------------

def get_panel() -> pd.DataFrame:
    """Long-format panel for the whole NSE equity universe. Rebuilt only when the trading day changes."""
    global _panel, _panel_day, _histories
    day = latest_trading_day()
    with _lock:
        if _panel is not None and (day is None or _panel_day == day):
            return _panel
        _building.set()
        try:
            started = time.monotonic()
            log.info("Building NSE market panel (latest trading day %s); missing days download from NSE", day)
            panel = nse_universe.build_market_panel()
            last = nse_universe.latest_trading_day(panel)
            _panel = panel
            _panel_day = last.date().isoformat() if last is not None else None
            _histories = {}
            log.info("Market panel ready: %d rows, %d symbols, last day %s, %.0fs",
                     len(panel), panel["symbol"].nunique() if not panel.empty else 0, _panel_day,
                     time.monotonic() - started)
        finally:
            _building.clear()
        _record_panel_day(_panel_day)
        return _panel


def set_panel(panel: pd.DataFrame) -> None:
    """Install a panel directly (tests, scripts). Clears per-symbol caches."""
    global _panel, _panel_day, _histories, _latest_day
    with _lock:
        _panel = panel
        last = nse_universe.latest_trading_day(panel)
        _panel_day = last.date().isoformat() if last is not None else None
        _histories = {}
        _latest_day = (_panel_day, time.monotonic())


def warm_up() -> None:
    """Build the panel in a background thread so the first run / Explore request is fast."""
    def _go():
        try:
            get_panel()
        except Exception:
            log.exception("Market panel warm-up failed")
    threading.Thread(target=_go, name="panel-warm-up", daemon=True).start()


def _record_panel_day(day: str | None) -> None:
    if not day:
        return
    try:
        from app.db.session import SessionLocal
        from app.models import AppMeta

        with SessionLocal() as db:
            db.merge(AppMeta(key="panel_built_for", value=day))
            db.commit()
    except Exception:
        log.warning("Could not record panel_built_for in app_meta", exc_info=True)


# --- per-symbol lookups ----------------------------------------------------------

def universe() -> list[str]:
    return nse_universe.universe_symbols(get_panel())


_HISTORY_COLUMNS = {"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume",
                    "deliv_pct": "DelivPct", "turnover_lacs": "TurnoverLacs"}


def to_histories(panel: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Long panel -> symbol -> OHLCV history (Open/High/Low/Close/Volume/DelivPct/TurnoverLacs), oldest first."""
    if panel.empty:
        return {}
    cols = [c for c in _HISTORY_COLUMNS if c in panel.columns]
    built = {}
    for sym, g in panel.groupby("symbol", sort=False):
        h = g.set_index("date")[cols]
        h.columns = [_HISTORY_COLUMNS[c] for c in cols]
        built[sym] = h
    return built


def all_histories() -> dict[str, pd.DataFrame]:
    """symbol -> history for the live panel, built in one groupby per panel."""
    global _histories
    panel = get_panel()
    with _lock:
        if not _histories and not panel.empty:
            _histories = to_histories(panel)
        return _histories


def histories_for_range(start: date, end: date, progress=None) -> dict[str, pd.DataFrame]:
    """Histories for any past range (backtests); missing bhavcopy days are downloaded and cached."""
    return to_histories(nse_universe.build_market_panel_range(start, end, progress=progress))


def history(symbol: str) -> pd.DataFrame:
    """OHLCV (+DelivPct) history with a DatetimeIndex, oldest first; empty DataFrame if unknown."""
    return all_histories().get(symbol.upper(), pd.DataFrame())


def latest_close(symbol: str) -> float | None:
    h = history(symbol)
    return float(h["Close"].iloc[-1]) if not h.empty else None


def close_on(symbol: str, on: str | date) -> tuple[str, float] | None:
    """(trading day, close) for the last session on or before `on`; None if no data that early."""
    h = history(symbol)
    if h.empty:
        return None
    upto = h.loc[h.index <= pd.Timestamp(on)]
    if upto.empty:
        return None
    return upto.index[-1].date().isoformat(), float(upto["Close"].iloc[-1])


# --- benchmark ---------------------------------------------------------------------

def _nifty_closes() -> pd.Series | None:
    key = date.today().isoformat()
    if key in _nifty:
        return _nifty[key]
    series = None
    try:
        import yfinance as yf

        hist = yf.Ticker("^NSEI").history(period="1y", interval="1d", auto_adjust=False)
        if not hist.empty:
            series = hist["Close"].copy()
            series.index = pd.to_datetime(series.index).tz_localize(None).normalize()
    except Exception:
        log.warning("NIFTY 50 fetch failed; benchmark unavailable", exc_info=True)
    _nifty.clear()
    _nifty[key] = series
    return series


def nifty_closes_range(start: date, end: date) -> pd.Series | None:
    """NIFTY 50 daily closes for [start, end] (yfinance); None on failure."""
    try:
        import yfinance as yf

        hist = yf.Ticker("^NSEI").history(start=start.isoformat(), end=(end + timedelta(days=1)).isoformat(),
                                          interval="1d", auto_adjust=False)
        if hist.empty:
            return None
        series = hist["Close"].copy()
        series.index = pd.to_datetime(series.index).tz_localize(None).normalize()
        return series
    except Exception:
        log.warning("NIFTY 50 range fetch failed; benchmark unavailable", exc_info=True)
        return None


def nifty_vs_ema50_pct(day: str | date) -> float | None:
    """Nifty 50 close vs its 50-day EMA on `day`, in % (None if Nifty data is unavailable)."""
    from app.engine.scoring.market_regime import nifty_vs_ema50_pct as compute

    return compute(_nifty_closes(), day)


def market_context(day: str | date) -> dict:
    """Whole-market facts the hard filters need for one trading day."""
    return {"nifty_vs_ema50_pct": nifty_vs_ema50_pct(day)}


def nifty_change_pct(from_date: str | date, to_date: str | date | None = None) -> float | None:
    """NIFTY 50 % change from the close on/before `from_date` to the close on/before `to_date`
    (default: latest). None on failure or when either end is unavailable."""
    closes = _nifty_closes()
    if closes is None or closes.empty:
        return None
    base = closes.loc[closes.index <= pd.Timestamp(from_date)]
    end = closes if to_date is None else closes.loc[closes.index <= pd.Timestamp(to_date)]
    if base.empty or end.empty or not base.iloc[-1]:
        return None
    return round((float(end.iloc[-1]) / float(base.iloc[-1]) - 1) * 100, 2)
