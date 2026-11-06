"""The stock dialog's decision: headline, findings for/against, expectation, review rule, backtest confidence and a
narrative. Deterministic from the verdict, plan, indicators and fundamentals already stored (docs/API_CONTRACT.md ->
Decision), rebuilt on every read so older rows work. Only the narrative comes from the LLM, and it is checked.
"""
import hashlib
import json
import re
import time
from collections.abc import Callable

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.engine import config as engine_config
from app.engine.agents import decision_narrator
from app.engine.data.indicators import compute_indicators
from app.engine.scoring.signal import SIGNALS
from app.models import Backtest, Suggestion
from app.services import market_data
from app.services.plan_service import display_date, exit_date_after, rupees

log = get_logger(__name__)

MIN_FINDINGS, MAX_FINDINGS, MAX_RULE_FINDINGS = 3, 6, 3
REVIEW_SESSIONS = 20                      # "20 trading days out"
FALLBACK_RETRY_S = 3600                   # like why_flagged: retry the LLM at most hourly
UP = {"STRONG_UPTREND", "ABOVE_200EMA", "UPTREND"}
DOWN = {"STRONG_DOWNTREND", "BELOW_200EMA", "DOWNTREND"}
SIGNAL_FIX = "the signal turns to Early Setup or Breakout"
_DIGIT = re.compile(r"\d")


def _num(x) -> float | None:
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if f == f else None


def _g(x: float) -> str:
    return f"{x:g}"


# --- context: every figure the decision may quote --------------------------------------------------------

def context(row: Suggestion, payload: dict) -> dict:
    ind = payload.get("indicators") or {}
    fund = payload.get("fundamentals") or {}
    vol = ((payload.get("pillars") or {}).get("volume_accumulation") or {}).get("details") or {}
    val = ((payload.get("pillars") or {}).get("valuation") or {}).get("details") or {}
    ctx = {
        "symbol": row.symbol, "price": row.price, "score": row.score, "signal": row.signal, "stage": row.stage,
        "entry_optimal": row.entry_optimal, "stop": row.stop_loss, "target": row.target,
        "planned_exit_date": row.planned_exit_date, "trading_day": row.trading_day,
        "ema_trend": ind.get("ema_trend"), "ema200": _num(ind.get("ema200")), "ema50": _num(ind.get("ema50")),
        "rsi": _num(ind.get("rsi")), "volume_ratio": _num(ind.get("volume_ratio")), "macd_signal": ind.get("macd_signal"),
        "pe": _num(fund.get("pe") if fund.get("pe") is not None else val.get("trailing_pe")),
        "latest_ocf": _num(fund.get("latest_ocf")), "market_cap": _num(fund.get("market_cap")),
        "profit_yoy_pct": _num(payload.get("profit_yoy_pct")),
        "deliv_recent": _num(vol.get("deliv_pct_recent_avg")), "deliv_prior": _num(vol.get("deliv_pct_prior_avg")),
        "low_20d": None, "high_52w": None, "macd_hist": None,
    }
    hist = market_data.history(row.symbol)
    if not hist.empty:
        hist = hist.loc[hist.index <= pd.Timestamp(row.trading_day)]  # what was known on the suggestion day
    if len(hist) >= 20:
        ctx["low_20d"] = float(hist["Low"].tail(20).min())
        ctx["high_52w"] = float(hist["Close"].tail(252).max())
        try:
            ctx["macd_hist"] = _num(compute_indicators(hist).get("macd_histogram"))
        except Exception:
            ctx["macd_hist"] = None
    return ctx


def _token(ctx: dict) -> str:
    return (ctx.get("ema_trend") or "").split(" ")[0]


# --- failed rules: the finding (with its figure) and the fix (a condition) --------------------------------------

Rule = tuple[re.Pattern, Callable[[re.Match, dict], str], Callable[[re.Match, dict], str]]


def _cr(x: float) -> str:
    return f"₹{x / 1e7:,.0f} Cr"


RULES: list[Rule] = [
    (re.compile(r"^Market cap bucket (.+) not in allowed \((.+)\)$"),
     lambda m, c: (f"Market cap {_cr(c['market_cap'])} ({m[1]}) is outside the allowed buckets ({m[2]})"
                   if c["market_cap"] else m[0]),
     lambda m, c: f"its market cap moves into an allowed bucket ({m[2]})"),
    (re.compile(r"^P/E (-?\d+) is negative \(loss-making\)$"),
     lambda m, c: f"P/E {m[1]}: the company is loss-making",
     lambda m, c: "the company returns to profit (a positive P/E)"),
    (re.compile(r"^P/E (\d+) above max (\d+)$"),
     lambda m, c: m[0],
     lambda m, c: (f"P/E falls under {m[2]} (price below {rupees(c['price'] * float(m[2]) / (c['pe'] or float(m[1])))})")),
    (re.compile(r"^ROE (-?[\d.]+)% below min (-?\d+)%$"),
     lambda m, c: m[0], lambda m, c: f"ROE reaches {m[2]}% or more in the next annual results"),
    (re.compile(r"^Debt/equity (\d+)% above max (\d+)%$"),
     lambda m, c: m[0], lambda m, c: f"debt/equity falls under {m[2]}%"),
    (re.compile(r"^Profit growth (-?\d+)% below min (-?\d+)%$"),
     lambda m, c: m[0], lambda m, c: f"the next quarterly results show profit growth of {m[2]}% or more"),
    (re.compile(r"^Operating cash flow is negative$"),
     lambda m, c: (f"Operating cash flow was {_cr(c['latest_ocf'])} in the latest year" if c["latest_ocf"] is not None
                   else "Operating cash flow is below 0 in the latest year"),
     lambda m, c: "operating cash flow turns positive in the next annual results"),
    (re.compile(r"^RSI (\d+) below min (\d+)$"),
     lambda m, c: m[0], lambda m, c: f"RSI rises back above {m[2]}"),
    (re.compile(r"^RSI (\d+) above max (\d+)$"),
     lambda m, c: m[0], lambda m, c: f"RSI drops back under {m[2]}"),
    (re.compile(r"^Price is below the 200-day EMA$"),
     lambda m, c: (f"Price {rupees(c['price'])} is below its 200-day EMA {rupees(c['ema200'])}" if c["ema200"]
                   else f"Price {rupees(c['price'])} is below its 200-day EMA"),
     lambda m, c: (f"it closes above the 200-day EMA ({rupees(c['ema200'])})" if c["ema200"]
                   else "it closes above the 200-day EMA")),
    (re.compile(r"^3-month run-up (\d+)% above max (\d+)%$"),
     lambda m, c: m[0], lambda m, c: f"the 3-month gain cools to under {m[2]}%"),
    (re.compile(r"^(\d+)% below 52-week high, more than max (\d+)%$"),
     lambda m, c: m[0],
     lambda m, c: (f"it climbs back within {m[2]}% of its 52-week high (above "
                   f"{rupees(c['high_52w'] * (1 - float(m[2]) / 100))})" if c["high_52w"]
                   else f"it climbs back within {m[2]}% of its 52-week high")),
    (re.compile(r"^Volume ([\d.]+)x 20-day average, below min ([\d.]+)x$"),
     lambda m, c: f"Volume {float(m[1]):.2f}× its 20-day average, below the {_g(float(m[2]))}× minimum",
     lambda m, c: f"volume runs above {_g(float(m[2]))}× its average for 3 sessions"),
    (re.compile(r"^Score (\d+) below min (\d+)$"),
     lambda m, c: f"Score {m[1]} of 100, below the minimum {m[2]}", lambda m, c: f"its score reaches {m[2]}"),
    (re.compile(r"^Signal is " + re.escape(SIGNALS["WEAK"]) + r"$"),
     lambda m, c: f"Signal is Weak (score {c['score']:.0f} of 100)", lambda m, c: SIGNAL_FIX),
    (re.compile(r"^Possible corporate action on (\S+), excluded$"),
     lambda m, c: f"Possible split or bonus on {m[1]}: price history not comparable",
     lambda m, c: f"130 sessions have passed since the possible corporate action on {m[1]}"),
    (re.compile(r"^No fundamentals available"),
     lambda m, c: "0 fundamental figures available (ETF, fund or data missing)",
     lambda m, c: "fundamentals become available"),
    (re.compile(r"^Nifty 50 is ([\d.]+)% below its 50-day EMA, more than max ([\d.]+)%"),
     lambda m, c: f"Nifty 50 is {m[1]}% below its 50-day EMA (limit {m[2]}%)",
     lambda m, c: f"Nifty 50 climbs back within {m[2]}% of its 50-day EMA"),
]


def rule_finding(failure: str, ctx: dict) -> str:
    for pattern, finding, _ in RULES:
        if m := pattern.search(failure):
            return finding(m, ctx)
    return failure


def rule_fix(failure: str, ctx: dict) -> str:
    for pattern, _, fix in RULES:
        if m := pattern.search(failure):
            return fix(m, ctx)
    return "the rule above is met"


def trend_fix(ctx: dict) -> str:
    if ctx["ema200"]:
        return f"it closes above the 200-day EMA ({rupees(ctx['ema200'])})"
    if ctx["ema50"]:
        return f"it closes above the 50-day EMA ({rupees(ctx['ema50'])})"
    return "the trend turns up"


# --- findings -----------------------------------------------------------------------------------------------------

def _chart_against(ctx: dict, failures: list[str]) -> list[str]:
    out, token, joined = [], _token(ctx), " ".join(failures)
    if token in ("BELOW_200EMA", "STRONG_DOWNTREND") and ctx["ema200"] and "200-day EMA" not in joined:
        out.append(f"Price {rupees(ctx['price'])} is below its 200-day EMA {rupees(ctx['ema200'])}")
    elif token == "DOWNTREND" and ctx["ema50"]:
        out.append(f"Price {rupees(ctx['price'])} is below its 50-day EMA {rupees(ctx['ema50'])}")
    if ctx["rsi"] is not None and ctx["rsi"] > 70 and "RSI" not in joined:
        out.append(f"RSI {ctx['rsi']:.0f} is above 70 (overbought)")
    if ctx["deliv_recent"] is not None and ctx["deliv_prior"] is not None and ctx["deliv_prior"] - ctx["deliv_recent"] >= 3:
        out.append(f"Delivery % fell from {ctx['deliv_prior']:.0f}% to {ctx['deliv_recent']:.0f}% over the last 10 sessions")
    if (ctx["macd_signal"] or "").startswith("BEARISH") and ctx["macd_hist"] is not None:
        out.append(f"MACD is bearish (histogram {ctx['macd_hist']:.2f})")
    if ctx["volume_ratio"] is not None and ctx["volume_ratio"] < 0.8 and "Volume" not in joined:
        out.append(f"Volume is only {ctx['volume_ratio']:.1f}× its 20-day average")
    return out


def _chart_for(ctx: dict) -> list[str]:
    token = _token(ctx)
    if token in ("STRONG_UPTREND", "ABOVE_200EMA") and ctx["ema200"]:
        return [f"Price {rupees(ctx['price'])} is above its 200-day EMA {rupees(ctx['ema200'])}"]
    if token == "UPTREND" and ctx["ema50"]:
        return [f"Price {rupees(ctx['price'])} is above its 50-day EMA {rupees(ctx['ema50'])}"]
    return []


def findings(overall: str, failures: list[str], positives: list[str], ctx: dict) -> list[dict]:
    """3-6 findings, each with a figure: failed rules first (max 3, verdict order); then for a buy the positives
    before the negative chart points, otherwise the negative chart points first."""
    rules = [{"side": "against", "text": rule_finding(f, ctx)} for f in failures[:MAX_RULE_FINDINGS]]
    against = [{"side": "against", "text": t} for t in _chart_against(ctx, failures)]
    pros = [{"side": "for", "text": p.rstrip(".")} for p in positives if _DIGIT.search(p)]
    pros += [{"side": "for", "text": t} for t in _chart_for(ctx)]
    ordered = rules + (pros + against if overall == "buy" else against + pros)
    padding = [
        {"side": "for" if overall != "avoid" else "against", "text": f"Score {ctx['score']:.0f} of 100"},
        *([{"side": "for" if 40 <= ctx["rsi"] <= 70 else "against", "text": f"RSI {ctx['rsi']:.0f}"}]
          if ctx["rsi"] is not None else []),
        *([{"side": "for" if ctx["volume_ratio"] >= 1 else "against",
            "text": f"Volume {ctx['volume_ratio']:.1f}× its 20-day average"}] if ctx["volume_ratio"] is not None else []),
    ]
    out, seen = [], set()
    for item in ordered + padding:
        if item["text"] in seen or not _DIGIT.search(item["text"]):
            continue
        if len(out) >= MAX_FINDINGS or (item in padding and len(out) >= MIN_FINDINGS):
            break
        seen.add(item["text"])
        out.append(item)
    return out


# --- headline, expectation, review ------------------------------------------------------------------------------

def _short(text: str) -> str:
    text = text.split(" — ")[0].rstrip(".")
    return text[0].lower() + text[1:] if len(text) > 1 and text[1].islower() else text


def _avoid_cause(failures_text: list[str], ctx: dict, trend: str) -> str:
    if failures_text:
        return failures_text[0]
    if ctx["profit_yoy_pct"] is not None and ctx["profit_yoy_pct"] < 0:
        return f"profit fell {abs(ctx['profit_yoy_pct']):.0f}% YoY"
    if ctx["signal"] == SIGNALS["WEAK"]:
        return f"the signal is Weak (score {ctx['score']:.0f} of 100)"
    return f"the chart is in a {trend}" if trend != "sideways" else "the chart is going sideways"


def headline(overall: str, label: str, trend: str, finds: list[dict], failures_text: list[str], ctx: dict) -> str:
    sym = ctx["symbol"]
    if overall == "buy":
        pro = next((f["text"] for f in finds if f["side"] == "for"), None)
        return f"Buy {sym} near {rupees(ctx['entry_optimal'])}: {label}" + (f", {_short(pro)}." if pro else ".")
    if overall == "watch":
        reason = failures_text[0] if failures_text else f"the chart is {trend} ({label})"
        return f"Wait on {sym}: {reason}."
    return f"Avoid {sym} for now: {_avoid_cause(failures_text, ctx, trend)}; {label}."


def _no_failure_fix(overall: str, ctx: dict, trend: str) -> str:
    if overall == "buy":
        return f"it closes below the stop at {rupees(ctx['stop'])}"
    if ctx["signal"] == SIGNALS["WEAK"]:
        return SIGNAL_FIX
    if trend != "uptrend":
        return trend_fix(ctx)
    if ctx["profit_yoy_pct"] is not None and ctx["profit_yoy_pct"] < 0:
        return "the next quarterly results show profit growing again"
    return SIGNAL_FIX


def expectation(overall: str, trend: str, failures: list[str], failures_text: list[str], ctx: dict) -> dict:
    later = exit_date_after(ctx["trading_day"], REVIEW_SESSIONS)
    fix = rule_fix(failures[0], ctx) if failures else _no_failure_fix(overall, ctx, trend)
    if overall == "buy":
        return {"direction": "up", "level": ctx["target"], "by_date": ctx["planned_exit_date"],
                "text": f"Expect {rupees(ctx['target'])} by {display_date(ctx['planned_exit_date'])} while it holds "
                        f"above {rupees(ctx['stop'])}."}
    if overall == "watch":
        return {"direction": "sideways", "level": ctx["entry_optimal"], "by_date": later,
                "text": f"Expect a pullback toward {rupees(ctx['entry_optimal'])}; becomes a Buy if it holds there "
                        f"and {fix}."}
    if trend == "downtrend":
        level = round(max(ctx["stop"], ctx["low_20d"]) if ctx["low_20d"] is not None else ctx["stop"], 2)
        return {"direction": "down", "level": level, "by_date": later,
                "text": f"Expect further weakness toward {rupees(level)} over the next 4 weeks."}
    return {"direction": "sideways", "level": None, "by_date": later,
            "text": "The price may hold up, but the numbers do not support buying: "
                    f"{_avoid_cause(failures_text, ctx, trend)}."}


def review(overall: str, trend: str, failures: list[str], ctx: dict, by_date: str) -> dict:
    trigger = rule_fix(failures[0], ctx) if failures else _no_failure_fix(overall, ctx, trend)
    return {"until": by_date, "trigger": trigger}


# --- confidence ------------------------------------------------------------------------------------------------------

def confidence(db: Session, profile_id: int, signal: str) -> dict:
    """The signal's win rate in the profile's latest finished backtest; all null when there is none."""
    bt = db.scalar(select(Backtest).where(Backtest.profile_id == profile_id, Backtest.status == "done")
                   .order_by(Backtest.id.desc()).limit(1))
    if bt is None:
        return {"signal_win_rate_pct": None, "trades": None, "backtest_id": None}
    rows = (json.loads(bt.breakdowns_json or "{}")).get("by_signal", [])
    row = next((r for r in rows if r.get("key") == signal), None)
    return {"signal_win_rate_pct": row["win_rate_pct"] if row else None, "trades": row["trades"] if row else 0,
            "backtest_id": bt.id}


# --- narrative ---------------------------------------------------------------------------------------------------------

def fallback_narrative(head: str, finds: list[dict]) -> str:
    return " ".join([head] + [f"{f['text']}." for f in finds[:2]])


def narrative(db: Session, row: Suggestion, head: str, finds: list[dict], expect: dict, rev: dict,
              allow_llm: bool) -> str:
    """LLM narrative cached on the row (key = the exact material it was written from, so new wording regenerates
    it); fallback text retried at most hourly. With allow_llm=False (lists) only the cache or the fallback is used."""
    review_for_llm = {**rev, "until_text": display_date(rev["until"])}
    material = decision_narrator.material_text(head, finds, expect, review_for_llm)
    key = hashlib.sha1(material.encode()).hexdigest()
    stored = {}
    if row.narration_json:
        try:
            stored = json.loads(row.narration_json)
        except ValueError:
            stored = {}
    cached = stored.get("decision") or {}
    if cached.get("key") == key and cached.get("text"):
        fresh = cached.get("source") == "llm" or time.time() - cached.get("at", 0) < FALLBACK_RETRY_S
        if fresh or not allow_llm or not engine_config.ANTHROPIC_API_KEY:
            return cached["text"]
    if not allow_llm:
        return fallback_narrative(head, finds)
    text, source = None, "fallback"
    if engine_config.ANTHROPIC_API_KEY:
        try:
            text = decision_narrator.narrate(head, finds, expect, review_for_llm)
        except Exception as exc:
            log.info("Decision narrative LLM error for %s: %s", row.symbol, exc)
        source = "llm" if text else "fallback"
    text = text or fallback_narrative(head, finds)
    stored["decision"] = {"text": text, "source": source, "at": int(time.time()), "key": key}
    row.narration_json = json.dumps(stored)
    db.commit()
    return text


# --- assembly ----------------------------------------------------------------------------------------------------------

def headline_for(row: Suggestion, payload: dict, verdict: dict) -> str:
    """Just the headline (SuggestionSummary.headline, rebuilt on read): no confidence lookup, no narrative."""
    ctx = context(row, payload)
    failures = list(verdict["rules"]["failures"])
    finds = findings(verdict["overall"], failures, json.loads(row.positives_json or "[]"), ctx)
    return headline(verdict["overall"], verdict["chart"]["label"], verdict["chart"]["trend"], finds,
                    [rule_finding(f, ctx) for f in failures], ctx)


def build(db: Session, row: Suggestion, payload: dict, verdict: dict, allow_llm: bool = False) -> dict:
    ctx = context(row, payload)
    overall, trend, label = verdict["overall"], verdict["chart"]["trend"], verdict["chart"]["label"]
    failures = list(verdict["rules"]["failures"])
    failures_text = [rule_finding(f, ctx) for f in failures]
    finds = findings(overall, failures, json.loads(row.positives_json or "[]"), ctx)
    head = headline(overall, label, trend, finds, failures_text, ctx)
    expect = expectation(overall, trend, failures, failures_text, ctx)
    rev = review(overall, trend, failures, ctx, expect["by_date"])
    return {
        "overall": overall, "headline": head, "findings": finds, "expectation": expect, "review": rev,
        "confidence": confidence(db, row.profile_id, row.signal),
        "narrative": narrative(db, row, head, finds, expect, rev, allow_llm),
    }
