"""Market context for a day from NSE: FII/DII cash flows (₹ crore) and index closes (with 1-day, 1-week and 1-month
changes), India VIX and Nifty 500 advance/decline. Both NSE endpoints are live-only; a reading is accepted only when NSE's own date is `day` (and,
for indices, the timestamp is after the 15:30 close), so an intraday number is never stored as a close.
"""
from datetime import date, datetime

from app.engine.data.sources.common import NSE, SourceUnavailable, cached, num, parse_date, safe

SOURCE = "market"
CLOSE_TIME = (15, 30)
BREADTH_INDEX = "NIFTY 500"


def _metric(day: date, key: str, value, unit: str = "") -> dict:
    return {"key": key, "date": day.isoformat(), "value": value, "unit": unit}


def flows(day: date) -> list[dict]:
    rows = NSE.get_json("https://www.nseindia.com/api/fiidiiTradeReact")
    if not isinstance(rows, list) or not rows:
        raise SourceUnavailable("unexpected FII/DII reply")
    out = []
    for r in rows:
        d = parse_date(r.get("date"))
        if d != day:
            raise SourceUnavailable(f"FII/DII figures are for {d}, not {day.isoformat()} (NSE shows the latest day only)")
        who = "fii" if "FII" in (r.get("category") or "").upper() else "dii"
        for part, field in (("buy", "buyValue"), ("sell", "sellValue"), ("net", "netValue")):
            out.append(_metric(day, f"{who}_{part}_cr", num(r.get(field)), "₹ cr"))
    return out


def indices(day: date) -> list[dict]:
    data = NSE.get_json("https://www.nseindia.com/api/allIndices")
    stamp = (data or {}).get("timestamp") if isinstance(data, dict) else None
    try:
        at = datetime.strptime(stamp.strip().title(), "%d-%b-%Y %H:%M")
    except (AttributeError, ValueError):
        raise SourceUnavailable("unexpected allIndices reply") from None
    if at.date() != day:
        raise SourceUnavailable(f"index data is for {at:%Y-%m-%d %H:%M}, not {day.isoformat()} (live endpoint)")
    if (at.hour, at.minute) < CLOSE_TIME:
        raise SourceUnavailable(f"index data is intraday ({at:%H:%M}); closes are published after 15:30")
    out = []
    for row in data.get("data") or []:
        name = (row.get("index") or "").strip()
        if not name:
            continue
        out.append(_metric(day, f"index:{name}:close", num(row.get("last")), "points"))
        out.append(_metric(day, f"index:{name}:pct_1d", num(row.get("percentChange")), "%"))
        last = num(row.get("last"))
        for span, field in (("pct_1w", "oneWeekAgoVal"), ("pct_1m", "oneMonthAgoVal")):
            base = num(row.get(field))
            if last is not None and base:
                out.append(_metric(day, f"index:{name}:{span}", round((last / base - 1) * 100, 2), "%"))
        if name == BREADTH_INDEX:
            adv, dec = num(row.get("advances")), num(row.get("declines"))
            out.append(_metric(day, "advances", adv, "stocks"))
            out.append(_metric(day, "declines", dec, "stocks"))
            out.append(_metric(day, "advance_decline", round(adv / dec, 3) if adv is not None and dec else None, "ratio"))
        if name == "INDIA VIX":
            out.append(_metric(day, "vix", num(row.get("last")), "points"))
    return out


def _fetch(day: date) -> list[dict]:
    out, problems = [], []
    for part in (flows, indices):
        try:
            out += part(day)
        except SourceUnavailable as e:
            problems.append(f"{part.__name__}: {e}")
    if not out:
        raise SourceUnavailable("; ".join(problems))
    return out + [{"key": "_warning", "date": day.isoformat(), "value": None, "unit": "", "note": p} for p in problems]


def fetch(day: date, use_cache: bool = True) -> list[dict]:
    return cached(SOURCE, day, _fetch, use_cache)


def pull(day: date) -> list[dict]:
    return safe(fetch, SOURCE, day)
