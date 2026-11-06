"""Builds the stock-dialog shapes (SuggestionSummary / SuggestionDetail) from scored data and stored suggestions.
Also the score breakdown, fundamentals mapping, indicators, price chart and the cached LLM narration.
"""
import json
import math
import time

import pandas as pd
import ta
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.engine import config as engine_config
from app.engine.agents import emerging_explainer
from app.engine.scoring.common import PillarResult
from app.engine.scoring.engine import PILLAR_ORDER, CandidateScore
from app.engine.scoring.signal import SIGNALS
from app.models import Position, Suggestion
from app.services import market_data
from app.services.plan_service import DISCLAIMER

log = get_logger(__name__)

CHART_ROWS = 130
INDICATOR_KEYS = ["rsi", "macd_signal", "ema_trend", "ema20", "ema50", "ema200", "atr", "bb_position", "volume_ratio"]


# --- value cleaning ----------------------------------------------------------

def num(value, digits: int = 2) -> float | None:
    """Finite float rounded, else None (never a fabricated 0)."""
    if value is None or isinstance(value, bool):
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return round(f, digits) if math.isfinite(f) else None


def _pct(value) -> float | None:
    f = num(value, 6)
    return round(f * 100, 2) if f is not None else None


def clean_details(details: dict) -> dict:
    out = {}
    for k, v in (details or {}).items():
        if isinstance(v, str) or v is None:
            out[k] = v
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            out[k] = num(v, 4) if isinstance(v, float) else int(v)
    return out


# --- pieces of the payload -------------------------------------------------------

def score_breakdown(candidate: CandidateScore, weights: dict) -> list[dict]:
    """Each pillar on the profile's weight scale: score = (points / max_points) x weight, max = weight."""
    rows = []
    for key, label in PILLAR_ORDER:
        p = candidate.pillars[key]
        w = float(weights.get(key, 0))
        avail = bool(p.available and p.score is not None)
        rows.append({
            "key": key, "label": label,
            "score": round(p.score / p.max_points * w, 1) if avail and p.max_points else None,
            "max": w, "weight": w, "available": avail,
            "details": clean_details(p.details),
        })
    return rows


def fundamentals(info: dict, candidate: CandidateScore) -> dict:
    info = info or {}
    earn = candidate.pillars["earnings_acceleration"].details
    fq = candidate.pillars["fundamental_quality"].details
    return {
        "pe": num(info.get("trailingPE")),
        "pb": num(info.get("priceToBook")),
        "roe_pct": _pct(info.get("returnOnEquity")),
        "debt_to_equity": num(info.get("debtToEquity")),
        "market_cap": num(info.get("marketCap"), 0),
        "sector": info.get("sector") or None,
        "industry": info.get("industry") or None,
        "revenue_yoy_pct": num(earn.get("revenue_yoy_pct")),
        "profit_yoy_pct": num(earn.get("profit_yoy_pct")),
        "eps_yoy_pct": num(earn.get("eps_yoy_pct")),
        "operating_margin_pct": _pct(info.get("operatingMargins")),
        "latest_ocf": num(fq.get("latest_ocf"), 0),
    }


def indicators(history: pd.DataFrame) -> dict:
    from app.engine.data.indicators import compute_indicators

    try:
        raw = compute_indicators(history) if history is not None and len(history) >= 20 else {}
    except Exception:
        log.debug("Indicators unavailable", exc_info=True)
        raw = {}
    out = {}
    for k in INDICATOR_KEYS:
        v = raw.get(k)
        out[k] = v if isinstance(v, str) else num(v)
    return out


def chart(history: pd.DataFrame, rows: int = CHART_ROWS) -> dict:
    if history is None or history.empty:
        return {"dates": [], "close": [], "ema20": [], "ema50": [], "volume": []}
    close = history["Close"].astype(float)
    ema20 = ta.trend.EMAIndicator(close, window=20).ema_indicator()
    ema50 = ta.trend.EMAIndicator(close, window=50).ema_indicator()
    tail = slice(-rows, None)
    return {
        "dates": [d.date().isoformat() for d in history.index[tail]],
        "close": [num(v) for v in close.iloc[tail]],
        "ema20": [num(v) for v in ema20.iloc[tail]],
        "ema50": [num(v) for v in ema50.iloc[tail]],
        "volume": [num(v, 0) for v in history["Volume"].iloc[tail]],
    }


def pillars_payload(candidate: CandidateScore) -> dict:
    return {k: {"score": num(p.score, 4), "max_points": p.max_points, "available": bool(p.available),
                "details": clean_details(p.details), "positives": list(p.positives), "risks": list(p.risks)}
            for k, p in candidate.pillars.items()}


# --- verdict (deterministic; docs/API_CONTRACT.md -> Verdict) ---------------------------------

UPTREND_TOKENS = {"STRONG_UPTREND", "ABOVE_200EMA", "UPTREND"}
DOWNTREND_TOKENS = {"STRONG_DOWNTREND", "BELOW_200EMA", "DOWNTREND"}
BUYABLE_SIGNALS = {SIGNALS["EARLY_SETUP"], SIGNALS["BREAKOUT_CONFIRMED"], SIGNALS["DEVELOPING"]}
# Signals whose meaning goes beyond the stage name; for the rest the stage reads better
# ("Uptrend, breakout confirmed", "Sideways, quiet accumulation", "Downtrend, weak").
SIGNAL_PHRASES = {SIGNALS["WEAK"]: "weak", SIGNALS["BREAKOUT_CONFIRMED"]: "breakout confirmed",
                  SIGNALS["EXTENDED"]: "extended"}


def _trend_token(ema_trend: str | None) -> str:
    return (ema_trend or "").split(" ")[0]  # "ABOVE_200EMA (bullish bias)" -> "ABOVE_200EMA"


def chart_trend(ema_trend: str | None) -> str:
    token = _trend_token(ema_trend)
    if token in UPTREND_TOKENS:
        return "uptrend"
    if token in DOWNTREND_TOKENS:
        return "downtrend"
    return "sideways"


def chart_points(ema_trend: str | None, rsi: float | None, volume_ratio: float | None) -> list[str]:
    token, points = _trend_token(ema_trend), []
    if token in ("STRONG_UPTREND", "ABOVE_200EMA"):
        points.append("Above 200-day EMA")
    elif token in ("STRONG_DOWNTREND", "BELOW_200EMA"):
        points.append("Below 200-day EMA")
    elif token == "UPTREND":   # history too short for a 200-day EMA
        points.append("Above 50-day EMA")
    elif token == "DOWNTREND":
        points.append("Below 50-day EMA")
    if rsi is not None:
        points.append(f"RSI {rsi:.0f}")
    if volume_ratio is not None:
        points.append(f"Volume {volume_ratio:.1f}x")
    return points


def verdict_reason(overall: str, failures: list[str], trend: str, label: str) -> str:
    """The contract's three sentences, word for word (docs/API_CONTRACT.md -> Verdict)."""
    if failures:
        return f"{failures[0]}; {label}."
    if overall == "avoid":
        return f"Passes all rules, but the chart is {trend}: {label}."
    return f"Passes all rules; {label}."


def build_verdict(failures: list[str], rules_total: int, signal: str, stage: str, ema_trend: str | None,
                  rsi: float | None, volume_ratio: float | None, profit_yoy_pct: float | None) -> dict:
    """overall / rules / chart / reason from already-computed numbers. Pure; no LLM."""
    failures = list(failures)
    trend = chart_trend(ema_trend)
    label = f"{trend.capitalize()}, {SIGNAL_PHRASES.get(signal, (stage or '').lower())}"
    if (signal == SIGNALS["WEAK"] or trend == "downtrend"
            or (profit_yoy_pct is not None and profit_yoy_pct < 0) or len(failures) > 2):
        overall = "avoid"
    elif not failures and trend == "uptrend" and signal in BUYABLE_SIGNALS:
        overall = "buy"
    else:
        overall = "watch"
    return {
        "overall": overall,
        "rules": {"passed": max(rules_total - len(failures), 0), "total": rules_total, "failures": failures},
        "chart": {"trend": trend, "label": label, "points": chart_points(ema_trend, rsi, volume_ratio)},
        "reason": verdict_reason(overall, failures, trend, label),
    }


def _verdict_of(row: Suggestion, payload: dict) -> dict:
    """Stored verdict, or computed once (and saved) for rows created before verdicts existed. The reason is
    rebuilt from the stored parts on every read, so a wording change in the contract reaches every row."""
    verdict = payload.get("verdict")
    if not verdict:
        from app.services import suggestion_service  # late import: suggestion_service imports this module

        verdict = suggestion_service.backfill_verdict(row)
    reason = verdict_reason(verdict["overall"], verdict["rules"]["failures"], verdict["chart"]["trend"],
                            verdict["chart"]["label"])
    return {**verdict, "reason": reason}


# --- narration -------------------------------------------------------------------

def _candidate_from_payload(row: Suggestion, payload: dict) -> CandidateScore:
    pillars = {k: PillarResult(score=v["score"], max_points=v["max_points"], available=v["available"],
                               details=v["details"], positives=v["positives"], risks=v["risks"])
               for k, v in payload.get("pillars", {}).items()}
    return CandidateScore(symbol=row.symbol, total_score=row.score, data_coverage=payload.get("data_coverage", 0.0),
                          pillars=pillars, stage=row.stage, signal=row.signal,
                          positives=json.loads(row.positives_json), risks=json.loads(row.risks_json),
                          profit_yoy_pct=payload.get("profit_yoy_pct"))


FALLBACK_RETRY_S = 3600  # retry the LLM for a fallback narration at most hourly


def narration(db: Session, row: Suggestion, payload: dict) -> dict:
    """{why_flagged, what_changed}: LLM narration of the stored numbers, cached on the row.
    Without ANTHROPIC_API_KEY, or when the LLM fails (e.g. rate limit), the explainer's deterministic fallback is
    returned; it is cached with a timestamp and the LLM is retried after FALLBACK_RETRY_S."""
    cached = None
    if row.narration_json:
        try:
            cached = json.loads(row.narration_json)
        except ValueError:
            cached = None
    if cached and cached.get("why_flagged"):
        if cached.get("source", "fallback") != "fallback":  # entries without a source predate this rule
            return {"why_flagged": cached["why_flagged"], "what_changed": cached.get("what_changed", "")}
        if not engine_config.ANTHROPIC_API_KEY or time.time() - cached.get("at", 0) < FALLBACK_RETRY_S:
            return {"why_flagged": cached["why_flagged"], "what_changed": cached.get("what_changed", "")}

    candidate = _candidate_from_payload(row, payload)
    source = "llm"
    text: dict = {}
    if engine_config.ANTHROPIC_API_KEY:
        try:
            result = emerging_explainer.call_llm_explain(candidate)
            if result is not None:
                text = result
        except Exception as exc:
            log.info("Narration LLM error for %s: %s", row.symbol, exc)
    if not text:
        source = "fallback"
        text = emerging_explainer._fallback_explanation(candidate)
    out = {"why_flagged": str(text.get("why_flagged") or ""), "what_changed": str(text.get("what_changed") or "")}
    row.narration_json = json.dumps({**out, "source": source, "at": int(time.time())})
    db.commit()
    return out


# --- tracking + shapes ---------------------------------------------------------------

def tracking_lookup(db: Session, profile_id: int) -> tuple[dict[int, int], dict[str, int]]:
    """(suggestion_id -> position_id, symbol -> open/due position_id) for one profile; newest position wins."""
    rows = db.execute(select(Position.id, Position.suggestion_id, Position.symbol, Position.status)
                      .where(Position.profile_id == profile_id).order_by(Position.id)).all()
    by_suggestion, open_by_symbol = {}, {}
    for pid, sid, sym, status in rows:
        if sid is not None:
            by_suggestion[sid] = pid
        if status in ("open", "due"):
            open_by_symbol[sym] = pid
    return by_suggestion, open_by_symbol


def summary(row: Suggestion, lookup: tuple[dict[int, int], dict[str, int]]) -> dict:
    payload = json.loads(row.payload_json or "{}")
    by_suggestion, open_by_symbol = lookup
    position_id = by_suggestion.get(row.id) or open_by_symbol.get(row.symbol)
    return {
        "id": row.id, "source": row.source, "verdict": _verdict_of(row, payload), "symbol": row.symbol,
        "rank": row.rank, "score": round(row.score, 1),
        "stage": row.stage, "signal": row.signal, "price": row.price, "entry_optimal": row.entry_optimal,
        "stop_loss": row.stop_loss, "target": row.target, "risk_reward": row.risk_reward,
        "horizon_days": row.horizon_days, "planned_exit_date": row.planned_exit_date,
        "market_cap_bucket": payload.get("market_cap_bucket", "Unknown"), "sector": payload.get("sector"),
        "profit_yoy_pct": payload.get("profit_yoy_pct"), "change_1m_pct": payload.get("change_1m_pct"),
        "change_3m_pct": payload.get("change_3m_pct"), "volume_ratio_20d": payload.get("volume_ratio_20d"),
        "is_tracked": position_id is not None, "position_id": position_id,
    }


def build_detail(db: Session, row: Suggestion) -> dict:
    payload = json.loads(row.payload_json or "{}")
    text = narration(db, row, payload)
    out = summary(row, tracking_lookup(db, row.profile_id))
    out.update({
        "trading_day": row.trading_day,
        "reasons": {"why_flagged": text["why_flagged"], "what_changed": text["what_changed"],
                    "positives": json.loads(row.positives_json), "risks": json.loads(row.risks_json)},
        "plan": {
            "entry_aggressive": row.entry_aggressive, "entry_optimal": row.entry_optimal,
            "entry_conservative": row.entry_conservative, "stop_loss": row.stop_loss, "target": row.target,
            "risk_reward": row.risk_reward, "horizon_days": row.horizon_days,
            "planned_exit_date": row.planned_exit_date, "timing_note": row.timing_note,
            "exit_note": row.exit_note, "disclaimer": DISCLAIMER,
        },
        "score_breakdown": payload.get("score_breakdown", []),
        "indicators": payload.get("indicators", {k: None for k in INDICATOR_KEYS}),
        "fundamentals": payload.get("fundamentals", {}),
        # The chart runs to the latest session so the dialog shows what happened after the suggestion.
        "chart": chart(market_data.history(row.symbol)),
        "filters": payload.get("filters", {"passed": True, "failures": []}),
    })
    return out
