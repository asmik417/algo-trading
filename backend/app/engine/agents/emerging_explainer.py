"""Turns an already-computed CandidateScore into plain-English narration.

This is the ONLY place in the Emerging Opportunities feature that touches an
LLM. It never calculates anything — every number it's allowed to mention is
handed to it pre-computed. The pipeline is strictly:

    raw data -> deterministic scoring (scoring/) -> LLM explains the result

not the other way around.
"""
import json

from app.engine.agents.base_agent import call_llm
from app.engine.scoring.engine import CandidateScore
from app.engine.utils.logger import get_logger

log = get_logger(__name__)

SYSTEM_PROMPT = """You are writing a short, plain-English research note for an Indian retail
investor about why a stock was flagged by a rules-based "Emerging Opportunities" scanner.
You are NOT analyzing anything yourself — every number below was already computed by a
deterministic scoring engine. Your only job is to narrate those numbers clearly and concisely.
Never invent a number that isn't given to you. Never give a buy/sell recommendation.
Always respond with valid JSON only."""


def _pillar_summary(candidate: CandidateScore) -> dict:
    out = {}
    for key, p in candidate.pillars.items():
        out[key] = {
            "score": round(p.score, 1) if p.score is not None else "unavailable",
            "max": p.max_points,
            "details": {k: (round(v, 2) if isinstance(v, float) else v) for k, v in p.details.items()},
        }
    return out


def explain(candidate: CandidateScore) -> dict:
    """Returns {"why_flagged": str, "what_changed": str}. Falls back to a
    deterministic template (no LLM) if the LLM call fails — the explanation
    always reflects the real computed numbers either way."""
    return call_llm_explain(candidate) or _fallback_explanation(candidate)


def call_llm_explain(candidate: CandidateScore) -> dict | None:
    """LLM narration only; None when the call fails or returns the wrong shape."""
    payload = {
        "symbol": candidate.symbol,
        "total_score": round(candidate.total_score, 1) if candidate.total_score is not None else None,
        "stage": candidate.stage,
        "signal": candidate.signal,
        "pillars": _pillar_summary(candidate),
        "positives": candidate.positives,
        "risks": candidate.risks,
    }

    user_prompt = f"""Here is the computed data for {candidate.symbol}:

{json.dumps(payload, indent=2, default=str)}

Return JSON with exactly these fields:
{{
  "why_flagged": "<2-3 sentences, data-backed, explaining specifically why this stock was flagged — reference the actual numbers given>",
  "what_changed": "<1-2 sentences on the single most important recent change, e.g. the latest quarter's numbers vs price reaction>"
}}"""

    try:
        result = call_llm(SYSTEM_PROMPT, user_prompt)
    except Exception as e:  # e.g. no API key configured
        log.info(f"LLM narration unavailable: {e}")
        return None
    if not isinstance(result, dict) or "error" in result or "why_flagged" not in result:
        return None
    return result


def _fallback_explanation(candidate: CandidateScore) -> dict:
    """Used only if the LLM call fails — built directly from the same
    computed fields, so it's never fabricated, just less polished prose."""
    earn = candidate.pillars["earnings_acceleration"].details
    pp = candidate.pillars["early_price_position"].details
    vol = candidate.pillars["volume_accumulation"].details

    profit, chg3m, volr = earn.get("profit_yoy_pct"), pp.get("change_3m_pct"), vol.get("volume_ratio_20d")
    parts = []
    if profit is not None:
        parts.append(f"net profit {'grew' if profit >= 0 else 'fell'} {abs(profit):.0f}% YoY")
    if chg3m is not None:
        parts.append(f"the stock is {'up' if chg3m >= 0 else 'down'} {abs(chg3m):.0f}% over 3 months")
    if volr is not None:
        parts.append(f"volume is at {volr:.1f}x its 20-day average")

    facts = "; ".join(parts) + "." if parts else ""
    why = f"{candidate.symbol} was flagged as {candidate.stage} ({candidate.signal}). " + (
        facts[:1].upper() + facts[1:] if facts else "Limited data was available for this stock."
    )

    if profit is not None and chg3m is not None:
        what = (f"Latest quarter profit {'grew' if profit >= 0 else 'fell'} {abs(profit):.0f}% YoY "
                f"while the stock moved {chg3m:+.0f}% over 3 months.")
    elif profit is not None:
        what = f"Latest quarter profit {'grew' if profit >= 0 else 'fell'} {abs(profit):.0f}% YoY."
    elif volr is not None:
        what = f"Trading volume is at {volr:.1f}x its 20-day average."
    else:
        what = "No recent change could be computed from the available data."
    return {"why_flagged": why, "what_changed": what}
