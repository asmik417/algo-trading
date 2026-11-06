"""Insider trades (SEBI PIT disclosures) from NSE's corporates-pit API, for disclosures dated `day`.
NSE always has insider disclosures over a week; an empty reply for the window means the endpoint refused us
(it needs a browser session), so it is reported as unavailable, never as "no insider trades".
"""
from datetime import date, timedelta

from app.engine.data.sources.common import NSE, SourceUnavailable, cached, nse_day, num, parse_date, safe

SOURCE = "insider"
WINDOW_DAYS = 7


def normalise(row: dict) -> dict | None:
    d = parse_date(row.get("intimDt") or row.get("date") or row.get("acqtoDt"))
    qty = num(row.get("secAcq"))
    if not row.get("symbol") or d is None or qty is None:
        return None
    kind = (row.get("tdpTransactionType") or row.get("acqMode") or "").strip()
    side = "buy" if kind.lower().startswith(("buy", "acq", "purchase")) else (
        "sell" if kind.lower().startswith(("sell", "sale", "dispos")) else None)
    value = num(row.get("secVal"))
    party = (row.get("acqName") or "").strip()
    return {"key": f"pit:{row['symbol']}:{d.isoformat()}:{party}:{kind}:{qty:g}", "symbol": row["symbol"],
            "date": d.isoformat(), "side": side, "party": party, "category": (row.get("personCategory") or "").strip(),
            "qty": qty, "value": value, "price": round(value / qty, 2) if value and qty else None, "mode": kind}


def _fetch(day: date) -> list[dict]:
    start = day - timedelta(days=WINDOW_DAYS - 1)
    data = NSE.get_json(f"https://www.nseindia.com/api/corporates-pit?index=equities&from_date={nse_day(start)}"
                        f"&to_date={nse_day(day)}")
    rows = data.get("data") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise SourceUnavailable("unexpected insider-trading reply")
    if not rows:
        raise SourceUnavailable(f"NSE returned no insider disclosures for {start.isoformat()}..{day.isoformat()}; "
                                "the endpoint needs a browser session")
    return [r for r in map(normalise, rows) if r and r["date"] == day.isoformat()]


def fetch(day: date, use_cache: bool = True) -> list[dict]:
    return cached(SOURCE, day, _fetch, use_cache)


def pull(day: date) -> list[dict]:
    return safe(fetch, SOURCE, day)
