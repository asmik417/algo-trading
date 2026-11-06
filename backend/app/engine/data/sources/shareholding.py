"""Shareholding patterns (promoter / public %) and promoter pledges filed on `day` (or over a look-back window,
used once to backfill), from NSE's share-holdings-master and pledgedata APIs. Quarterly by nature.
FII and DII shares are not in NSE's summary, so they stay unavailable here.
"""
from datetime import date, timedelta

from app.engine.data.sources.common import (NSE, SourceUnavailable, cached, known_names, nse_day, num, parse_date,
                                            remember_names, safe)

SOURCE = "shareholding"


def normalise_pattern(row: dict) -> dict | None:
    filed = parse_date(row.get("broadcastDate") or row.get("submissionDate"))
    as_of = parse_date(row.get("date"))
    if not row.get("symbol") or filed is None:
        return None
    return {"key": f"pattern:{row['symbol']}:{as_of}:{row.get('recordId') or filed}", "symbol": row["symbol"],
            "kind": "pattern", "filed_on": filed.isoformat(), "as_of": as_of.isoformat() if as_of else None,
            "promoter_pct": num(row.get("pr_and_prgrp")), "public_pct": num(row.get("public_val")),
            "employee_trust_pct": num(row.get("employeeTrusts")), "pledge_pct": None, "promoter_holding_pct": None}


def normalise_pledge(row: dict, symbols_by_name: dict[str, str]) -> dict | None:
    filed = parse_date(row.get("broadcastDt"))
    symbol = row.get("symbol") or symbols_by_name.get((row.get("comName") or "").strip().lower())
    if not symbol or filed is None:
        return None
    as_of = parse_date(row.get("shp") or row.get("disclosureToDate"))
    return {"key": f"pledge:{symbol}:{filed.isoformat()}:{row.get('numSharesPledged')}", "symbol": symbol,
            "kind": "pledge", "filed_on": filed.isoformat(), "as_of": as_of.isoformat() if as_of else None,
            "promoter_pct": None, "public_pct": None, "employee_trust_pct": None,
            "pledge_pct": num(row.get("percSharesPledged")), "promoter_holding_pct": num(row.get("percPromoterHolding"))}


def fetch_window(start: date, end: date) -> list[dict]:
    rng = f"index=equities&from_date={nse_day(start)}&to_date={nse_day(end)}"
    patterns = NSE.get_json(f"https://www.nseindia.com/api/corporate-share-holdings-master?{rng}")
    if not isinstance(patterns, list):
        raise SourceUnavailable("unexpected shareholding reply")
    out = [r for r in map(normalise_pattern, patterns) if r]
    remember_names({p.get("name") or "": p.get("symbol") or "" for p in patterns})
    names = known_names()
    pledges = NSE.get_json(f"https://www.nseindia.com/api/corporate-pledgedata?{rng}")
    rows = pledges.get("data") if isinstance(pledges, dict) else None
    out += [r for r in (normalise_pledge(p, names) for p in rows or []) if r]
    return [r for r in out if start.isoformat() <= r["filed_on"] <= end.isoformat()]


def _fetch(day: date) -> list[dict]:
    return fetch_window(day, day)


def fetch(day: date, use_cache: bool = True, lookback_days: int = 0) -> list[dict]:
    if lookback_days:  # one-off backfill: not cached per day (it spans many days)
        return fetch_window(day - timedelta(days=lookback_days), day)
    return cached(SOURCE, day, _fetch, use_cache)


def pull(day: date) -> list[dict]:
    return safe(fetch, SOURCE, day)
