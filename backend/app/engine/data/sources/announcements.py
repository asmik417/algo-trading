"""Corporate announcements for a day plus the upcoming event calendar (results dates, board meetings),
from NSE's corporate-announcements and event-calendar APIs.
"""
from datetime import date, timedelta

from app.engine.data.sources.common import (NSE, SourceUnavailable, cached, nse_day, parse_date, parse_datetime,
                                            remember_names, safe)

SOURCE = "announcements"
CALENDAR_DAYS_AHEAD = 14


def normalise_announcement(a: dict) -> dict | None:
    d = parse_date(a.get("an_dt") or a.get("sort_date"))
    if not a.get("symbol") or d is None:
        return None
    return {"key": f"ann:{a.get('seq_id') or a.get('dt')}:{a['symbol']}", "symbol": a["symbol"], "date": d.isoformat(),
            "at": parse_datetime(a.get("an_dt")), "kind": (a.get("desc") or "").strip(),
            "title": (a.get("attchmntText") or "").strip(), "url": a.get("attchmntFile") or None, "source": "nse"}


def normalise_event(e: dict) -> dict | None:
    d = parse_date(e.get("date"))
    if not e.get("symbol") or d is None:
        return None
    return {"key": f"event:{e['symbol']}:{d.isoformat()}:{(e.get('purpose') or '').strip()}", "symbol": e["symbol"],
            "date": d.isoformat(), "at": None, "kind": f"Upcoming: {(e.get('purpose') or '').strip()}",
            "title": (e.get("bm_desc") or "").strip(), "url": None, "source": "nse"}


def _fetch(day: date) -> list[dict]:
    anns = NSE.get_json(f"https://www.nseindia.com/api/corporate-announcements?index=equities"
                        f"&from_date={nse_day(day)}&to_date={nse_day(day)}")
    if not isinstance(anns, list):
        raise SourceUnavailable("unexpected announcements reply")
    events = NSE.get_json(f"https://www.nseindia.com/api/event-calendar?index=equities&from_date={nse_day(day)}"
                          f"&to_date={nse_day(day + timedelta(days=CALENDAR_DAYS_AHEAD))}")
    remember_names({a.get("sm_name") or "": a.get("symbol") or "" for a in anns})
    remember_names({e.get("company") or "": e.get("symbol") or "" for e in events if isinstance(events, list)})
    out = [r for r in map(normalise_announcement, anns) if r and r["date"] == day.isoformat()]
    out += [r for r in map(normalise_event, events if isinstance(events, list) else []) if r]
    return out


def fetch(day: date, use_cache: bool = True) -> list[dict]:
    return cached(SOURCE, day, _fetch, use_cache)


def pull(day: date) -> list[dict]:
    return safe(fetch, SOURCE, day)
