"""Shared plumbing for the source pullers: a browser-like, throttled HTTP session (NSE refuses plain clients),
the on-disk cache data/cache/sources/<source>/<day>.json, small parsers, and the never-raise wrapper.
"""
import json
import os
import threading
import time
from collections.abc import Callable
from datetime import date, datetime

import requests

from app.engine import config
from app.engine.utils.logger import get_logger

log = get_logger(__name__)

CACHE_DIR = os.path.join(config.BACKEND_DIR, "data", "cache", "sources")
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/130.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}
RETRIES = 3
BACKOFF_S = 2.0
_sleep = time.sleep  # replaced in tests


class SourceUnavailable(Exception):
    """The source could not provide data for the day; the message says why (recorded in source_pulls)."""


class ThrottledSession:
    """requests.Session with browser headers, at least `min_interval` seconds between request starts (shared by
    all threads using it) and retries with backoff on network errors, 429 and 5xx."""

    def __init__(self, min_interval: float = 1.0, headers: dict | None = None, timeout: float = 25.0):
        self.min_interval, self.timeout = min_interval, timeout
        self._session = requests.Session()
        self._session.headers.update(headers or BROWSER_HEADERS)
        self._next = 0.0
        self._lock = threading.Lock()

    def _wait_turn(self) -> None:
        with self._lock:
            now = time.monotonic()
            start = max(now, self._next)
            self._next = start + self.min_interval
        if start > now:
            _sleep(start - now)

    def get(self, url: str, **kwargs) -> requests.Response:
        last: Exception | None = None
        for attempt in range(RETRIES + 1):
            self._wait_turn()
            try:
                r = self._session.get(url, timeout=self.timeout, **kwargs)
                if r.status_code == 429 or r.status_code >= 500:
                    raise SourceUnavailable(f"HTTP {r.status_code} from {url.split('?')[0]}")
                if r.status_code >= 400:
                    raise SourceUnavailable(f"HTTP {r.status_code} from {url.split('?')[0]}")
                return r
            except SourceUnavailable as e:
                last = e
                if "HTTP 4" in str(e) and "HTTP 429" not in str(e):
                    raise  # 4xx other than 429 will not get better by retrying
            except requests.RequestException as e:
                last = SourceUnavailable(f"{type(e).__name__} from {url.split('?')[0]}")
            if attempt < RETRIES:
                _sleep(BACKOFF_S * 2 ** attempt)
        raise last  # type: ignore[misc]

    def get_json(self, url: str):
        r = self.get(url)
        try:
            return r.json()
        except ValueError:
            raise SourceUnavailable(f"non-JSON reply from {url.split('?')[0]}") from None


# One session per site, shared by every puller: NSE allows roughly one request a second from a client.
NSE = ThrottledSession(min_interval=1.0)
WEB = ThrottledSession(min_interval=1.0, headers={**BROWSER_HEADERS, "Accept": "application/rss+xml, text/xml, */*"})


# --- cache ---------------------------------------------------------------------------------------------------

def cache_path(source: str, day: date) -> str:
    return os.path.join(CACHE_DIR, source, f"{day.isoformat()}.json")


def read_cache(source: str, day: date) -> list[dict] | None:
    path = cache_path(source, day)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def write_cache(source: str, day: date, records: list[dict]) -> None:
    path = cache_path(source, day)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{threading.get_ident()}.tmp"
    with open(tmp, "w") as f:
        json.dump(records, f, ensure_ascii=False)
    os.replace(tmp, path)


def cached(source: str, day: date, fetch: Callable[[date], list[dict]], use_cache: bool = True) -> list[dict]:
    """Cache-first: a day already pulled successfully is never fetched again (live-only endpoints cannot be)."""
    if use_cache and (hit := read_cache(source, day)) is not None:
        return hit
    records = fetch(day)
    write_cache(source, day, records)
    return records


def safe(fetch: Callable[[date], list[dict]], source: str, day: date) -> list[dict]:
    """pull(): the never-raising form of fetch()."""
    try:
        return fetch(day)
    except Exception as e:
        log.warning("Source %s for %s unavailable: %s", source, day, e)
        return []


# --- company name -> symbol (some NSE feeds, e.g. pledges, name the company but not the symbol) -------------

_names_lock = threading.Lock()


def _names_path() -> str:
    return os.path.join(CACHE_DIR, "company_names.json")


def known_names() -> dict[str, str]:
    try:
        with open(_names_path()) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def remember_names(pairs: dict[str, str]) -> None:
    """Merge {company name: symbol} into the on-disk map (names lower-cased, trimmed)."""
    clean = {k.strip().lower(): v for k, v in pairs.items() if k and v}
    if not clean:
        return
    with _names_lock:
        merged = {**known_names(), **clean}
        os.makedirs(CACHE_DIR, exist_ok=True)
        tmp = f"{_names_path()}.{threading.get_ident()}.tmp"
        with open(tmp, "w") as f:
            json.dump(merged, f, ensure_ascii=False)
        os.replace(tmp, _names_path())


# --- parsing -------------------------------------------------------------------------------------------------

def nse_day(day: date) -> str:
    return day.strftime("%d-%m-%Y")


def parse_date(text) -> date | None:
    """NSE writes dates many ways: 05-Nov-2026, 05-NOV-2026, 05-Nov-2026 23:59:08, 2026-11-05, 30-SEP-2026."""
    if not text:
        return None
    s = str(text).strip()
    for fmt in ("%d-%b-%Y %H:%M:%S", "%d-%b-%Y %H:%M", "%d-%b-%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y",
                "%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"):
        try:
            return datetime.strptime(s.title() if "%b" in fmt and fmt.startswith("%d") else s, fmt).date()
        except ValueError:
            continue
    return None


def parse_datetime(text) -> str | None:
    """'05-Nov-2026 23:59:08' -> '2026-11-05T23:59:08' (IST, as NSE publishes it)."""
    if not text:
        return None
    s = str(text).strip().title()
    for fmt in ("%d-%b-%Y %H:%M:%S", "%d-%b-%Y %H:%M"):
        try:
            return datetime.strptime(s, fmt).isoformat()
        except ValueError:
            continue
    return None


def num(value) -> float | None:
    """'1,22,500' / ' 48.20 ' / '-' / None -> float or None (never 0 for missing)."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value) if value == value else None
    s = str(value).replace(",", "").strip()
    if s in ("", "-", "--", "NA", "N/A", "nil", "Nil", "null"):
        return None
    try:
        return float(s)
    except ValueError:
        return None
