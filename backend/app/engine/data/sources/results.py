"""Point-in-time quarterly results: every financial-results filing NSE broadcast on `day` (the SEBI "Integrated
Filing - Financials" feed), with its filing timestamp, and the quarter's figures parsed from the filing's XBRL.
filed_on is what lets backtests use only results that were public on a scan date.
"""
import re
from datetime import date
from urllib.parse import quote

from app.engine.data.sources.common import NSE, SourceUnavailable, cached, nse_day, num, parse_date, parse_datetime, safe

SOURCE = "results"
PAGE_SIZE = 500
FEED = ("https://www.nseindia.com/api/integrated-filing-results?index=equities&from_date={d}&to_date={d}"
        "&type=Integrated%20Filing-%20Financials&page={page}&size={size}")
SYMBOL_FEED = "https://www.nseindia.com/api/integrated-filing-results?index=equities&symbol={s}&page=1&size=100"
FINANCIALS = "Integrated Filing- Financials"
# First tag present wins. Banks file InterestEarned instead of RevenueFromOperations (not yet seen in a live filing).
TAGS = {
    "revenue": ("RevenueFromOperations", "InterestEarned", "Income"),
    "net_profit": ("ProfitLossForPeriod", "ProfitOrLossAttributableToOwnersOfParent", "ProfitLossForThePeriod"),
    "eps": ("BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations",
            "BasicEarningsLossPerShareFromContinuingOperations"),
    "pbt": ("ProfitBeforeTax",),
    "finance_costs": ("FinanceCosts",),
    "depreciation": ("DepreciationDepletionAndAmortisationExpense",),
    "other_income": ("OtherIncome",),
}
_CONTEXT = re.compile(r'<xbrli:context id="([^"]+)">(.*?)</xbrli:context>', re.S)


def quarter_context(xbrl: str, period_end: str) -> str | None:
    """The context covering exactly the quarter (about 3 months ending period_end) with no dimension member."""
    for cid, body in _CONTEXT.findall(xbrl):
        if "explicitMember" in body or "typedMember" in body:
            continue
        start = re.search(r"<xbrli:startDate>([^<]+)</xbrli:startDate>", body)
        end = re.search(r"<xbrli:endDate>([^<]+)</xbrli:endDate>", body)
        if not start or not end or end.group(1).strip() != period_end:
            continue
        days = (date.fromisoformat(end.group(1).strip()) - date.fromisoformat(start.group(1).strip())).days
        if 80 <= days <= 100:
            return cid
    return None


def parse_xbrl(xbrl: str, period_end: str) -> dict:
    """Quarter figures in rupees (EPS in rupees per share); EBITDA = PBT + finance costs + depreciation - other
    income; margin_pct = EBITDA / revenue. Missing elements stay None."""
    cid = quarter_context(xbrl, period_end)
    if cid is None:
        return {"period_start": None, "revenue": None, "ebitda": None, "net_profit": None, "eps": None,
                "margin_pct": None, "parse_error": f"no quarter context ending {period_end}"}
    values = {}
    for field, tags in TAGS.items():
        values[field] = None
        for tag in tags:
            m = re.search(rf'<[a-zA-Z\-]+:{tag}\b[^>]*contextRef="{re.escape(cid)}"[^>]*>([^<]*)<', xbrl)
            if m and num(m.group(1)) is not None:
                values[field] = num(m.group(1))
                break
    parts = (values["pbt"], values["finance_costs"], values["depreciation"])
    ebitda = (sum(parts) - (values["other_income"] or 0)) if all(v is not None for v in parts) else None
    start = re.search(rf'<xbrli:context id="{re.escape(cid)}">.*?<xbrli:startDate>([^<]+)<', xbrl, re.S)
    revenue = values["revenue"]
    return {"period_start": start.group(1).strip() if start else None, "revenue": revenue, "ebitda": ebitda,
            "net_profit": values["net_profit"], "eps": values["eps"],
            "margin_pct": round(ebitda / revenue * 100, 2) if ebitda is not None and revenue else None,
            "parse_error": None}


def filings(day: date) -> list[dict]:
    out, page = [], 1
    while True:
        data = NSE.get_json(FEED.format(d=nse_day(day), page=page, size=PAGE_SIZE))
        rows = data.get("data") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            raise SourceUnavailable("unexpected results-feed reply")
        out += rows
        total = data.get("totalCount") or 0
        if not rows or len(out) >= total:
            return out
        page += 1


def normalise(f: dict, xbrl_text: str | None) -> dict | None:
    period_end = parse_date(f.get("qe_Date"))
    filed_at = parse_datetime(f.get("broadcast_Date") or f.get("creation_Date"))
    if not f.get("symbol") or period_end is None or filed_at is None:
        return None
    figures = parse_xbrl(xbrl_text, period_end.isoformat()) if xbrl_text else {
        "period_start": None, "revenue": None, "ebitda": None, "net_profit": None, "eps": None, "margin_pct": None,
        "parse_error": "XBRL not fetched"}
    return {"key": f"nse:{f.get('seq_Id')}", "symbol": f["symbol"], "period_end": period_end.isoformat(),
            "filed_on": filed_at[:10], "filed_at": filed_at, "nature": f.get("consolidated"),
            "audited": f.get("audited"), "revision": f.get("type_Sub"), "xbrl_url": f.get("xbrl"), **figures}


def _fetch(day: date) -> list[dict]:
    out = []
    for f in filings(day):
        text = None
        if f.get("xbrl"):
            try:
                text = NSE.get(f["xbrl"]).text
            except SourceUnavailable:
                text = None  # the filing date is still worth keeping; figures stay None
        row = normalise(f, text)
        if row and row["filed_on"] == day.isoformat():
            out.append(row)
    return out


def _preferred(f: dict) -> tuple:
    """Sort key: consolidated before standalone, then the latest broadcast (a revision replaces the original)."""
    return (f.get("consolidated") == "Consolidated", parse_datetime(f.get("broadcast_Date")) or "")


def symbol_history(symbol: str, quarters: int = 5) -> list[dict]:
    """The latest `quarters` quarterly results one company filed (one filing per quarter, consolidated preferred),
    each with its filing date and XBRL figures. Used to give a followed stock its recent quarters on first sight.
    Raises SourceUnavailable when NSE does not answer."""
    data = NSE.get_json(SYMBOL_FEED.format(s=quote(symbol.upper(), safe="")))
    rows = data.get("data") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise SourceUnavailable("unexpected results-feed reply")
    best: dict[date, dict] = {}
    for f in rows:
        period_end = parse_date(f.get("qe_Date"))
        if f.get("type") != FINANCIALS or period_end is None or not f.get("broadcast_Date"):
            continue
        if period_end not in best or _preferred(f) > _preferred(best[period_end]):
            best[period_end] = f
    out = []
    for period_end in sorted(best, reverse=True)[:quarters]:
        f, text = best[period_end], None
        if f.get("xbrl"):
            try:
                text = NSE.get(f["xbrl"]).text
            except SourceUnavailable:
                text = None
        row = normalise(f, text)
        if row:
            out.append(row)
    return out


def fetch(day: date, use_cache: bool = True) -> list[dict]:
    return cached(SOURCE, day, _fetch, use_cache)


def pull(day: date) -> list[dict]:
    return safe(fetch, SOURCE, day)
