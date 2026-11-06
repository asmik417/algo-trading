"""Evidence packs (docs/API_CONTRACT.md -> Evidence pack): one stock on one day, from the engine's indicators, the
source tables and the market context. Point-in-time (nothing filed after the day); every gap is listed in unavailable.
"""
import json
import math
from datetime import date, timedelta

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.engine.data import index_history
from app.engine.data.sources import common, news, results
from app.models import (Announcement, Deal, EvidencePackRow, InsiderTrade, NewsItem, QuarterlyResult, Shareholding,
                        SourcePull, Suggestion)
from app.services import (analysis_service, market_brief_service, market_data, plan_service, profile_service,
                          source_service)
from app.services.errors import NotFound

log = get_logger(__name__)

QUARTERS = 5                 # latest five quarters: the newest one has its year-ago quarter alongside
MIN_QUARTERS = 4             # fewer filed quarters than this triggers a one-off history fetch for the stock
DEALS_DAYS = 30
EVENTS_PAST_DAYS = 30
EVENTS_AHEAD_DAYS = 30
HEADLINE_DAYS = 7
MAX_EVENTS, MAX_DEALS, MAX_HEADLINES = 25, 20, 15
CRORE = 1e7
_history_tried: set[tuple[str, str]] = set()   # (symbol, calendar day): fetch a stock's results history once a day


def _f(x, digits: int = 2) -> float | None:
    if x is None:
        return None
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return round(x, digits) if math.isfinite(x) else None


# --- sector: Yahoo's sector/industry -> the NSE sector index the stock is compared with -----------------------------

def sector_index(sector: str | None, industry: str | None) -> str | None:
    s, i = (sector or "").lower(), (industry or "").lower()
    if not s:
        return None
    if s == "technology":
        return "NIFTY IT"
    if s == "financial services":
        return "NIFTY BANK" if "bank" in i else "NIFTY FINANCIAL SERVICES"
    if s == "healthcare":
        return "NIFTY PHARMA" if any(w in i for w in ("drug", "pharma", "biotech")) else "NIFTY HEALTHCARE INDEX"
    if s == "consumer defensive":
        return "NIFTY FMCG"
    if s == "consumer cyclical":
        if "auto" in i:
            return "NIFTY AUTO"
        if any(w in i for w in ("furnish", "appliance", "electronic", "home")):
            return "NIFTY CONSUMER DURABLES"
        return "NIFTY INDIA CONSUMPTION"
    if s == "basic materials":
        if any(w in i for w in ("chemical", "agricultural")):
            return "NIFTY CHEMICALS"
        if "building" in i:
            return "NIFTY CEMENT"
        return "NIFTY METAL"
    if s in ("energy", "utilities"):
        return "NIFTY ENERGY"
    if s == "real estate":
        return "NIFTY REALTY"
    if s == "communication services":
        return "NIFTY MEDIA"
    if s == "industrials":
        return "NIFTY INFRASTRUCTURE"
    return None


def _sector_of(symbol: str, day: str, payload: dict | None) -> str | None:
    """From the stored suggestion's sector and the day's fundamentals (Yahoo sector and industry)."""
    from app.services import suggestion_service  # late import: suggestion_service imports much of the app

    try:
        info = (suggestion_service.load_fundamentals(day, symbol) or {}).get("info") or {}
    except Exception:
        log.debug("No fundamentals for %s on %s", symbol, day, exc_info=True)
        info = {}
    return sector_index((payload or {}).get("sector") or info.get("sector"), info.get("industry"))


# --- sections -------------------------------------------------------------------------------------------------------------

def _change(series: pd.Series, sessions: int) -> float | None:
    if len(series) <= sessions or not series.iloc[-1 - sessions]:
        return None
    return _f((float(series.iloc[-1]) / float(series.iloc[-1 - sessions]) - 1) * 100)


def price_section(hist: pd.DataFrame, day: str, sector_name: str | None, moves: dict) -> dict:
    close = hist["Close"].astype(float)
    ind = analysis_service.indicators(hist)
    out = {"close": _f(close.iloc[-1]), "change_1w_pct": _change(close, 5), "change_1m_pct": _change(close, 21),
           "change_3m_pct": _change(close, 63)}
    # Relative strength in percentage points over the same 21 sessions (a stock bar date -> the index close on/before it).
    nifty = index_history.upto(index_history.closes("NIFTY 50"), day)
    out["vs_nifty_1m_pct"] = None
    if out["change_1m_pct"] is not None and nifty is not None and len(close) > 21:
        base = nifty.loc[nifty.index <= close.index[-22]]
        if not base.empty and nifty.index[-1].date().isoformat() == day and base.iloc[-1]:
            out["vs_nifty_1m_pct"] = _f(out["change_1m_pct"] - (float(nifty.iloc[-1]) / float(base.iloc[-1]) - 1) * 100)
    sector_1m = (moves.get(sector_name) or {}).get("pct_1m") if sector_name else None
    out["vs_sector_1m_pct"] = _f(out["change_1m_pct"] - sector_1m) if out["change_1m_pct"] is not None and sector_1m is not None else None
    high = float(close.tail(252).max())
    out["dist_52w_high_pct"] = _f((float(close.iloc[-1]) / high - 1) * 100) if high else None
    out["volume_ratio"] = ind.get("volume_ratio")
    deliv = hist["DelivPct"].astype(float) if "DelivPct" in hist else None
    now = deliv.iloc[-1] if deliv is not None else None
    prev = deliv.iloc[-21:-1].dropna() if deliv is not None else None
    out["delivery_pct_now"] = _f(now)
    out["delivery_pct_prev"] = _f(prev.mean()) if prev is not None and len(prev) >= 10 else None
    out["ema_trend"] = ind.get("ema_trend") if isinstance(ind.get("ema_trend"), str) else None
    out["rsi"] = ind.get("rsi")
    return out


def quarters_section(db: Session, symbol: str, day: str) -> list[dict]:
    """Latest QUARTERS quarters filed on or before `day`; per quarter the consolidated filing, latest revision."""
    rows = db.scalars(select(QuarterlyResult).where(QuarterlyResult.symbol == symbol, QuarterlyResult.filed_on <= day))
    best: dict[str, QuarterlyResult] = {}
    for r in rows:
        key = (r.nature == "Consolidated", r.filed_on, r.id)
        cur = best.get(r.period_end)
        if cur is None or key > (cur.nature == "Consolidated", cur.filed_on, cur.id):
            best[r.period_end] = r
    out = []
    for period in sorted(best, reverse=True)[:QUARTERS]:
        r = best[period]
        out.append({"period": period, "filed_on": r.filed_on, "revenue": _f(r.revenue / CRORE) if r.revenue is not None else None,
                    "ebitda": _f(r.ebitda / CRORE) if r.ebitda is not None else None,
                    "net_profit": _f(r.net_profit / CRORE) if r.net_profit is not None else None,
                    "eps": _f(r.eps), "margin_pct": _f(r.margin_pct)})
    return out


def ensure_quarters(db: Session, symbol: str, day: str) -> str | None:
    """Fetch the stock's recent quarterly results once a day when fewer than MIN_QUARTERS are stored; the rows are
    stored insert-only like the nightly pull. Returns an error note when NSE did not answer."""
    have = {p for (p,) in db.execute(select(QuarterlyResult.period_end).where(QuarterlyResult.symbol == symbol,
                                                                              QuarterlyResult.filed_on <= day))}
    key = (symbol, date.today().isoformat())
    if len(have) >= MIN_QUARTERS or key in _history_tried:
        return None
    _history_tried.add(key)
    try:
        rows = results.symbol_history(symbol, QUARTERS)
    except Exception as e:
        return f"results history: {e}"
    source_service.persist(db, "results", date.fromisoformat(day), rows)
    return None


def ownership_section(db: Session, symbol: str, day: str) -> dict | None:
    rows = list(db.scalars(select(Shareholding).where(Shareholding.symbol == symbol, Shareholding.filed_on <= day)))
    patterns = sorted((r for r in rows if r.kind == "pattern"), key=lambda r: (r.as_of or "", r.filed_on, r.id),
                      reverse=True)
    pledges = sorted((r for r in rows if r.kind == "pledge"), key=lambda r: (r.filed_on, r.as_of or "", r.id),
                     reverse=True)
    if not patterns and not pledges:
        return None
    latest = patterns[0] if patterns else None
    earlier = next((p for p in patterns[1:] if latest and p.as_of and latest.as_of and p.as_of < latest.as_of), None)
    change = None
    if latest is not None and earlier is not None and latest.promoter_pct is not None and earlier.promoter_pct is not None:
        change = _f(latest.promoter_pct - earlier.promoter_pct)
    return {"as_of": latest.as_of if latest else (pledges[0].as_of if pledges else None),
            "promoter_pct": _f(latest.promoter_pct) if latest else None, "promoter_change_pct": change,
            "fii_pct": None, "dii_pct": None,   # NSE's shareholding master gives promoter and public only
            "public_pct": _f(latest.public_pct) if latest else None,
            "pledge_pct": _f(pledges[0].pledge_pct) if pledges else None}


def deals_section(db: Session, symbol: str, day: str) -> list[dict]:
    start = (date.fromisoformat(day) - timedelta(days=DEALS_DAYS)).isoformat()
    out = [{"date": d.date, "kind": d.kind, "party": d.party, "qty": d.qty, "price": _f(d.price)}
           for d in db.scalars(select(Deal).where(Deal.symbol == symbol, Deal.date > start, Deal.date <= day))
           if d.kind in ("bulk", "block")]
    out += [{"date": t.date, "kind": f"insider_{t.side}", "party": t.party, "qty": t.qty, "price": _f(t.price)}
            for t in db.scalars(select(InsiderTrade).where(InsiderTrade.symbol == symbol, InsiderTrade.date > start,
                                                          InsiderTrade.date <= day))
            if t.side in ("buy", "sell")]
    return sorted(out, key=lambda r: (r["date"], r["party"]), reverse=True)[:MAX_DEALS]


def events_section(db: Session, symbol: str, day: str) -> list[dict]:
    """Announcements of the last 30 days, plus calendar events ahead that were known by `day`."""
    d = date.fromisoformat(day)
    past_start = (d - timedelta(days=EVENTS_PAST_DAYS)).isoformat()
    ahead_end = (d + timedelta(days=EVENTS_AHEAD_DAYS)).isoformat()
    rows = db.scalars(select(Announcement).where(Announcement.symbol == symbol, Announcement.date > past_start,
                                                 Announcement.date <= ahead_end, Announcement.pulled_day <= day))
    seen, ahead, past = set(), [], []
    for r in sorted(rows, key=lambda r: (r.date, r.at or "", r.id), reverse=True):
        item = {"date": r.date, "kind": r.kind, "title": r.title}
        if (item["date"], item["kind"], item["title"]) in seen:
            continue
        seen.add((item["date"], item["kind"], item["title"]))
        (ahead if r.date > day else past).append(item)
    return ahead[::-1] + past[:MAX_EVENTS]


def headlines_section(db: Session, symbol: str, day: str) -> list[dict]:
    start = (date.fromisoformat(day) - timedelta(days=HEADLINE_DAYS - 1)).isoformat()
    rows = db.scalars(select(NewsItem).where(NewsItem.symbol == symbol, NewsItem.date >= start, NewsItem.date <= day)
                      .order_by(NewsItem.date.desc(), NewsItem.id.desc()))
    out, seen = [], set()
    for r in rows:
        if r.title in seen:
            continue
        seen.add(r.title)
        out.append({"date": r.date, "title": r.title, "source": r.source, "url": r.url})
    return out[:MAX_HEADLINES]


def fetch_headlines(db: Session, symbol: str, day: str) -> bool:
    """On-demand Google News for one stock (latest day only); True when the fetch answered."""
    names = {s: n for n, s in common.known_names().items()}
    try:
        rows = news.company_items(symbol, (names.get(symbol) or symbol).title(), date.fromisoformat(day))
    except Exception:
        log.info("On-demand headlines for %s unavailable", symbol, exc_info=True)
        return False
    source_service.persist(db, "news", date.fromisoformat(day), rows)
    return True


def _pulled_ok(db: Session, source: str, start: str, day: str) -> bool:
    return db.scalar(select(SourcePull.id).where(SourcePull.source == source, SourcePull.day >= start,
                                                 SourcePull.day <= day, SourcePull.status.in_(("ok", "empty")))
                     .limit(1)) is not None


def rules_section(db: Session, symbol: str, day: str, hist: pd.DataFrame,
                  profile=None) -> tuple[dict | None, dict | None, dict | None]:
    """(verdict, plan, stored payload). With no `profile` (the pack): the stored suggestion for this stock and day,
    active strategy first, newest first. With a `profile` (the analyst): only that profile's stored suggestion.
    Failing that, the strategy's rules run on the history up to `day` (not saved)."""
    from app.services import suggestion_service

    if profile is None:
        try:
            active = profile_service.get_active(db)
        except NotFound:
            active = None
    else:
        active = profile
    q = select(Suggestion).where(Suggestion.symbol == symbol, Suggestion.trading_day == day)
    if profile is not None:
        q = q.where(Suggestion.profile_id == profile.id)
    rows = list(db.scalars(q.order_by(Suggestion.id.desc())))
    rows.sort(key=lambda r: active is not None and r.profile_id == active.id, reverse=True)
    if rows:
        row = rows[0]
        payload = json.loads(row.payload_json or "{}")
        verdict = analysis_service._verdict_of(row, payload)
        plan = {"entry_aggressive": row.entry_aggressive, "entry_optimal": row.entry_optimal,
                "entry_conservative": row.entry_conservative, "stop_loss": row.stop_loss, "target": row.target,
                "risk_reward": row.risk_reward, "horizon_days": row.horizon_days,
                "planned_exit_date": row.planned_exit_date, "timing_note": row.timing_note,
                "exit_note": row.exit_note, "disclaimer": plan_service.DISCLAIMER}
        return verdict, plan, payload
    if active is None:
        return None, None, None
    try:
        params = profile_service.params_of(active)
        market = market_data.market_context(day) if params.min_nifty_vs_ema50_pct > 0 else {}
        s = suggestion_service.score_symbol(symbol, hist, suggestion_service.load_fundamentals(day, symbol), params,
                                            market=market)
        if s.candidate.total_score is None:
            return None, None, None
        verdict = suggestion_service.verdict_of(s)
        plan = plan_service.build_plan(hist, s.candidate.stage, params, day)
        info = s.bundle.get("info") or {}
        return verdict, (plan.to_dict() if plan else None), {"sector": info.get("sector")}
    except Exception:
        log.info("Rules verdict for %s on %s unavailable", symbol, day, exc_info=True)
        return None, None, None


# --- build ------------------------------------------------------------------------------------------------------------

def build(db: Session, symbol: str, day: str, fetch_missing: bool = True, brief_context: tuple[dict, dict] | None = None) -> dict:
    """Build, store and return the pack. `fetch_missing` lets it fetch a stock's quarterly history (and, for the
    latest day, its headlines) when the tables have none. Raises NotFound when the stock did not trade on `day`."""
    sym = symbol.strip().upper()
    hist = market_data.history(sym)
    hist = hist.loc[hist.index <= pd.Timestamp(day)] if not hist.empty else hist
    if hist.empty or hist.index[-1] != pd.Timestamp(day):
        raise NotFound(f"{sym} did not trade on {day}.")
    unavailable: list[str] = []
    ctx, extras = brief_context or market_brief_service.context(db, day)
    verdict, plan, payload = rules_section(db, sym, day, hist)
    sector = _sector_of(sym, day, payload)
    moves = extras["moves"]
    market = {**ctx, "sector_index": sector,
              "sector_1w_pct": (moves.get(sector) or {}).get("pct_1w") if sector else None}
    price = price_section(hist, day, sector, moves)

    if fetch_missing:
        note = ensure_quarters(db, sym, day)
        if note:
            log.info("Evidence %s %s: %s", sym, day, note)
    quarters = quarters_section(db, sym, day)
    ownership = ownership_section(db, sym, day)
    deals = deals_section(db, sym, day)
    events = events_section(db, sym, day)
    headlines = headlines_section(db, sym, day)
    fetched_news = False
    if not headlines and fetch_missing and day == market_data.panel_day():
        fetched_news = fetch_headlines(db, sym, day)
        headlines = headlines_section(db, sym, day)

    window = lambda days: (date.fromisoformat(day) - timedelta(days=days)).isoformat()  # noqa: E731
    unavailable += [f"price.{k}" for k, v in price.items() if v is None]
    if not quarters:
        unavailable.append("quarters")
    if ownership is None:
        unavailable.append("ownership")
    else:
        unavailable += [f"ownership.{k}" for k, v in ownership.items() if v is None]
    if not _pulled_ok(db, "deals", window(DEALS_DAYS), day):
        unavailable.append("deals")
    if not _pulled_ok(db, "insider", window(DEALS_DAYS), day):
        unavailable.append("deals.insider")
    if not _pulled_ok(db, "announcements", window(EVENTS_PAST_DAYS), day):
        unavailable.append("events")
    if not headlines and not fetched_news:
        unavailable.append("headlines")
    unavailable += [f"market.{k}" for k, v in market.items() if v is None]
    if verdict is None:
        unavailable.append("rules_verdict")
    if plan is None:
        unavailable.append("plan")

    pack = {"symbol": sym, "day": day, "price": price, "quarters": quarters, "ownership": ownership, "deals": deals,
            "events": events, "headlines": headlines, "market": market, "rules_verdict": verdict, "plan": plan,
            "unavailable": unavailable}
    return save(db, pack)


def save(db: Session, pack: dict) -> dict:
    """Store (or replace) the pack for its (symbol, day)."""
    row = db.scalar(select(EvidencePackRow).where(EvidencePackRow.symbol == pack["symbol"],
                                                  EvidencePackRow.day == pack["day"]))
    if row is None:
        row = EvidencePackRow(symbol=pack["symbol"], day=pack["day"], pack_json="{}")
        db.add(row)
    row.pack_json = json.dumps(pack, ensure_ascii=False)
    db.commit()
    return pack


def get(db: Session, symbol: str, day: date | None = None) -> dict:
    sym = symbol.strip().upper()
    q = select(EvidencePackRow).where(EvidencePackRow.symbol == sym)
    q = q.where(EvidencePackRow.day == day.isoformat()) if day else q.order_by(EvidencePackRow.day.desc())
    row = db.scalar(q.limit(1))
    if row is None:
        raise NotFound(f"No evidence pack for {sym}" + (f" on {day.isoformat()}." if day else "."))
    return json.loads(row.pack_json)


def build_now(db: Session, symbol: str) -> dict:
    """POST /stocks/{symbol}/evidence: build for the latest trading day, fetching what is missing."""
    day = market_data.panel_day()
    if not day:
        raise NotFound("Market data is not available yet.")
    return build(db, symbol, day, fetch_missing=True)
