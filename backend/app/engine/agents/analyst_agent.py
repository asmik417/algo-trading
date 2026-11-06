"""The analyst (docs/BRAIN_PLAN.md -> the method): Claude reasons over one evidence pack in five fixed steps and returns
strict JSON. A separate small call may web-search the stock's news; only the search tool's own results are kept.
"""
import json
import re
from datetime import date, datetime, timedelta
from urllib.parse import urlparse

import anthropic

from app.engine import config
from app.engine.agents.base_agent import get_client
from app.engine.utils.logger import get_logger

log = get_logger(__name__)

MAX_TOKENS = 16000
NEWS_MAX_TOKENS = 2000
NEWS_SEARCHES = 2
HOLDING_ACTIONS = ["add", "hold", "trim", "exit"]
NEW_ACTIONS = ["buy", "watch", "avoid"]
# USD per million tokens: input, output, cache read, cache write (5-minute); and per web search.
PRICES = {"claude-opus-5-5": (4.0, 20.0, 0.20, 5.0)}
WEB_SEARCH_USD = 0.01

# No digits here except the fixed horizon and the sideways band, which the audit allows (FIXED_NUMBERS). It also
# allows the numbers that are names in the pack's field names, not figures: Nifty 50, S&P 500, the 50- and 200-day
# EMAs and the 52-week high (on the first real run, 16 of 18 answers were re-asked only for writing "S&P 500").
FIXED_NUMBERS = (20, 5, 50, 52, 200, 500)
SYSTEM_PROMPT = """You are a careful equity analyst for an Indian retail swing trader who trades paper money and holds a
position for about 20 trading sessions. You are given one stock's evidence pack for one day, computed by code: price
and trend, quarterly results with their filing dates, ownership, deals, events, headlines, the market context, the
trader's strategy's rules verdict and plan, and derived figures. Fields listed under "unavailable" are unknown, not
zero; never guess them.

Follow this method exactly, in this order:
1. Observe. List only facts from the evidence, each with its figure and its date where one is given.
2. What is odd. List anomalies: price moving against the fundamentals, volume without news, delivery percentage
   falling in a rally, promoter selling or pledging, insider buying, results delayed, sector moving without the stock,
   and anything else that does not fit. An empty list is allowed when nothing is odd.
3. Two stories. Write the bull case and the bear case, each as a causal chain from the evidence to the price.
4. Try to kill both. For each story's key claims, state what evidence would prove it wrong and whether that evidence
   is present, absent or unknown in the pack.
5. Verdict. Give the direction over the next 20 sessions (up, down, or sideways meaning within five percent either
   way), an action from the allowed list, a confidence (low, medium or high), the trigger that would flip your call,
   and the one thing you most want to know that the evidence does not show.

Rules for numbers: every number you write must be copied from the evidence exactly as given (you may round it to
fewer decimals). Do not compute new numbers: no differences, ratios, growth rates or averages of your own; the
derived section already holds the computed ones. Write dates as they appear in the evidence. Do not invent prices,
targets or dates; the plan's levels are the only levels. Your opinion is shown next to the rules verdict and scored
later; it does not change the plan. Be concrete and brief; no generic advice."""


def _schema(actions: list[str]) -> dict:
    text = {"type": "string"}
    return {
        "type": "object",
        "properties": {
            "observations": {"type": "array", "items": text},
            "anomalies": {"type": "array", "items": text},
            "bull_case": text,
            "bear_case": text,
            "tests": {"type": "array", "items": {
                "type": "object",
                "properties": {"claim": text, "evidence": {"type": "string", "enum": ["present", "absent", "unknown"]},
                               "note": text},
                "required": ["claim", "evidence", "note"], "additionalProperties": False}},
            "action": {"type": "string", "enum": actions},
            "direction": {"type": "string", "enum": ["up", "down", "sideways"]},
            "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
            "trigger": text,
            "want_to_know": text,
        },
        "required": ["observations", "anomalies", "bull_case", "bear_case", "tests", "action", "direction",
                     "confidence", "trigger", "want_to_know"],
        "additionalProperties": False,
    }


TEXT_FIELDS = ("observations", "anomalies", "bull_case", "bear_case", "trigger", "want_to_know")


def texts_of(view: dict) -> list[str]:
    """Every free-text string in a view, for the number audit."""
    out: list[str] = []
    for key in TEXT_FIELDS:
        value = view.get(key)
        out += value if isinstance(value, list) else [value or ""]
    for t in view.get("tests") or []:
        out += [t.get("claim") or "", t.get("note") or ""]
    return [t for t in out if isinstance(t, str)]


# --- usage and cost -----------------------------------------------------------------------------------------------------

def empty_usage() -> dict:
    return {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0,
            "web_search_requests": 0, "calls": 0}


def add_usage(total: dict, usage) -> dict:
    if usage is None:
        return total
    for key in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"):
        total[key] += int(getattr(usage, key, 0) or 0)
    server = getattr(usage, "server_tool_use", None)
    total["web_search_requests"] += int(getattr(server, "web_search_requests", 0) or 0) if server else 0
    total["calls"] += 1
    return total


def cost_usd(usage: dict, model: str) -> float | None:
    price = PRICES.get(model)
    if price is None:
        return None
    p_in, p_out, p_read, p_write = price
    tokens = (usage["input_tokens"] * p_in + usage["output_tokens"] * p_out
              + usage["cache_read_input_tokens"] * p_read + usage["cache_creation_input_tokens"] * p_write) / 1e6
    return round(tokens + usage["web_search_requests"] * WEB_SEARCH_USD, 5)


# --- news search (web search used for nothing else) ---------------------------------------------------------------

_AGO = re.compile(r"(\d+)\s+(minute|hour|day|week)s?\s+ago", re.I)
_ISO = re.compile(r"\d{4}-\d{2}-\d{2}")
_WORDS = re.compile(r"([A-Za-z]{3,9})\.? (\d{1,2}),? (\d{4})")


def page_date(page_age: str | None, today: date) -> date | None:
    """The date in a search result's page_age ('November 4, 2026', '2026-11-04T10:00:00', '3 days ago')."""
    if not page_age:
        return None
    m = _AGO.search(page_age)
    if m:
        n, unit = int(m.group(1)), m.group(2).lower()
        return today - timedelta(days={"minute": 0, "hour": n // 24, "day": n, "week": 7 * n}[unit])
    m = _ISO.search(page_age)
    if m:
        try:
            return date.fromisoformat(m.group(0))
        except ValueError:
            return None
    m = _WORDS.search(page_age)
    if m:
        for fmt in ("%B %d %Y", "%b %d %Y"):
            try:
                return datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", fmt).date()
            except ValueError:
                continue
    return None


def search_news(symbol: str, company: str, day: date, window_days: int = 7) -> tuple[list[dict], dict, str | None]:
    """(headlines, usage, error). Headlines come only from the search tool's result blocks (title, url, page age),
    never from the model's text, and only those dated within the window up to `day`."""
    usage = empty_usage()
    if not config.ANTHROPIC_API_KEY:
        return [], usage, "ANTHROPIC_API_KEY not set"
    prompt = (f"Use web search to find news published in the last seven days about {company} (NSE symbol {symbol}) "
              "and its shares. Search only for this company's news. When you have searched, reply with: done.")
    try:
        msg = get_client().messages.create(
            model=config.ANALYST_MODEL, max_tokens=NEWS_MAX_TOKENS, output_config={"effort": "low"},
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": NEWS_SEARCHES,
                    "user_location": {"type": "approximate", "country": "IN"}}],
            messages=[{"role": "user", "content": prompt}])
    except anthropic.APIError as e:
        return [], usage, f"news search failed: {type(e).__name__}"
    add_usage(usage, msg.usage)
    start = day - timedelta(days=window_days - 1)
    out, seen = [], set()
    for block in msg.content:
        if getattr(block, "type", "") != "web_search_tool_result" or not isinstance(block.content, list):
            continue
        for r in block.content:
            url, title = getattr(r, "url", None), (getattr(r, "title", None) or "").strip()
            when = page_date(getattr(r, "page_age", None), date.today())
            if not url or not title or when is None or not (start <= when <= day) or url in seen:
                continue
            seen.add(url)
            out.append({"date": when.isoformat(), "title": title, "source": urlparse(url).netloc.removeprefix("www."),
                        "url": url, "via": "web_search"})
    return out, usage, None


# --- the reasoning call ---------------------------------------------------------------------------------------------

def user_prompt(evidence: dict, actions: list[str], previous: dict | None = None, bad: list[str] | None = None) -> str:
    text = ("Evidence pack (JSON):\n" + json.dumps(evidence, ensure_ascii=False, separators=(",", ":"))
            + f"\n\nAllowed actions: {', '.join(actions)}.")
    if previous is not None:
        text += ("\n\nYour previous answer wrote numbers that are not in the evidence: " + ", ".join(bad or [])
                 + ". Rewrite the whole answer without them, copying every number from the evidence.\nPrevious answer: "
                 + json.dumps(previous, ensure_ascii=False))
    return text


def reason(evidence: dict, actions: list[str], previous: dict | None = None,
           bad: list[str] | None = None) -> tuple[dict | None, dict, str | None, str]:
    """(view fields or None, usage, error, model that answered)."""
    usage = empty_usage()
    if not config.ANTHROPIC_API_KEY:
        return None, usage, "ANTHROPIC_API_KEY not set", config.ANALYST_MODEL
    try:
        msg = get_client().messages.create(
            model=config.ANALYST_MODEL, max_tokens=MAX_TOKENS, system=SYSTEM_PROMPT,
            thinking={"type": "adaptive"},
            output_config={"effort": config.ANALYST_EFFORT,
                           "format": {"type": "json_schema", "schema": _schema(actions)}},
            messages=[{"role": "user", "content": user_prompt(evidence, actions, previous, bad)}])
    except anthropic.APIError as e:
        log.error("Analyst call failed (%s): %s", type(e).__name__, e)
        return None, usage, f"{type(e).__name__}", config.ANALYST_MODEL
    add_usage(usage, msg.usage)
    model = getattr(msg, "model", None) or config.ANALYST_MODEL
    if msg.stop_reason != "end_turn":
        return None, usage, f"stop_reason {msg.stop_reason}", model
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    try:
        data = json.loads(text)
    except ValueError:
        return None, usage, "reply was not JSON", model
    if not isinstance(data, dict) or data.get("action") not in actions:
        return None, usage, "reply did not match the schema", model
    return data, usage, None, model
