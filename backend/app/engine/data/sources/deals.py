"""Bulk and block deals from NSE's large-deal snapshot. NSE publishes only the latest session (its historical
endpoint refuses scripted clients), so a day other than the snapshot's own date is reported as unavailable.
"""
from datetime import date

from app.engine.data.sources.common import NSE, SourceUnavailable, cached, num, parse_date, safe

SOURCE = "deals"
URL = "https://www.nseindia.com/api/snapshot-capital-market-largedeal"


def normalise(row: dict, kind: str) -> dict | None:
    d = parse_date(row.get("date"))
    qty = num(row.get("qty"))
    if not row.get("symbol") or d is None or qty is None:
        return None
    side = (row.get("buySell") or "").upper() or None
    party = (row.get("clientName") or "").strip()
    price = num(row.get("watp"))
    return {"key": f"{kind}:{d.isoformat()}:{row['symbol']}:{party}:{side}:{qty:g}:{price}", "symbol": row["symbol"],
            "date": d.isoformat(), "kind": kind, "side": side, "party": party, "qty": qty, "price": price}


def _fetch(day: date) -> list[dict]:
    data = NSE.get_json(URL)
    as_on = parse_date((data or {}).get("as_on_date")) if isinstance(data, dict) else None
    if as_on is None:
        raise SourceUnavailable("unexpected large-deal reply")
    if as_on != day:
        raise SourceUnavailable(f"NSE publishes deals for the latest session only (as on {as_on.isoformat()})")
    out = []
    for key, kind in (("BULK_DEALS_DATA", "bulk"), ("BLOCK_DEALS_DATA", "block")):
        out += [r for r in (normalise(row, kind) for row in data.get(key) or []) if r and r["date"] == day.isoformat()]
    return out


def fetch(day: date, use_cache: bool = True) -> list[dict]:
    return cached(SOURCE, day, _fetch, use_cache)


def pull(day: date) -> list[dict]:
    return safe(fetch, SOURCE, day)
