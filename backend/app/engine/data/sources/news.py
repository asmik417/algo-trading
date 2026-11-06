"""News headlines: Economic Times market RSS feeds for `day`, plus Google News RSS per company for the stocks the
brain follows (last 7 days up to `day`). Titles and links only; nothing is summarised here. (Moneycontrol's RSS feeds
have not been updated since April 2024, so they are not used.)
"""
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote

from app.engine.data.sources.common import WEB, SourceUnavailable, cached, safe

SOURCE = "news"
IST = timezone(timedelta(hours=5, minutes=30))
MARKET_FEEDS = {
    "ET Markets": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "ET Stocks": "https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms",
}
COMPANY_WINDOW_DAYS = 7


def google_news_url(company: str) -> str:
    return f"https://news.google.com/rss/search?q={quote(company + ' share')}&hl=en-IN&gl=IN&ceid=IN:en"


def parse_rss(xml_text: str, default_source: str) -> list[dict]:
    """[{title, url, source, date (IST)}] from an RSS 2.0 document."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        raise SourceUnavailable(f"{default_source}: not an RSS document") from None
    items = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        when = item.findtext("pubDate")
        try:
            at = parsedate_to_datetime(when).astimezone(IST) if when else None
        except (TypeError, ValueError):
            at = None
        if not title or not link or at is None:
            continue
        items.append({"title": title, "url": link, "source": (item.findtext("source") or default_source).strip(),
                      "date": at.date().isoformat(), "at": at.isoformat()})
    return items


def _fetch(day: date, companies: dict[str, str] | None = None) -> list[dict]:
    out, problems = [], []
    for name, url in MARKET_FEEDS.items():
        try:
            items = parse_rss(WEB.get(url).text, name)
            out += [{**i, "key": i["url"], "symbol": None} for i in items if i["date"] == day.isoformat()]
        except SourceUnavailable as e:
            problems.append(f"{name}: {e}")
    start = (day - timedelta(days=COMPANY_WINDOW_DAYS - 1)).isoformat()
    for symbol, company in (companies or {}).items():
        try:
            items = parse_rss(WEB.get(google_news_url(company or symbol)).text, "Google News")
            out += [{**i, "key": f"{symbol}:{i['url']}", "symbol": symbol} for i in items
                    if start <= i["date"] <= day.isoformat()]
        except SourceUnavailable as e:
            problems.append(f"{symbol}: {e}")
    if not out and problems:
        raise SourceUnavailable("; ".join(problems[:5]))
    return out + [{"key": "_warning", "date": day.isoformat(), "note": p} for p in problems]


def fetch(day: date, use_cache: bool = True, companies: dict[str, str] | None = None) -> list[dict]:
    return cached(SOURCE, day, lambda d: _fetch(d, companies), use_cache)


def pull(day: date, companies: dict[str, str] | None = None) -> list[dict]:
    return safe(lambda d: fetch(d, companies=companies), SOURCE, day)
