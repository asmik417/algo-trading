"""The decision narrative: a short plain-English paragraph written by the LLM from the decision's own headline,
findings, expectation and review, and nothing else. Any number in the reply that is not in that material is
rejected (None), so the caller falls back to deterministic text.
"""
import json
import re

from app.engine.agents.base_agent import call_llm

# No digits in the instructions: every number the model sees comes from the material.
SYSTEM_PROMPT = """You explain a stock decision to someone who does not trade. You are given the decision as
written by a rules-based system: a headline, findings for and against, what we expect, and when to look again.
Write two to four short sentences in plain English that say what we are doing and why, then what we expect.
Use only the facts and numbers you are given; never add a number, a price, a date or a fact of your own.
Do not give generic investment advice. Respond with valid JSON only: {"narrative": "..."}"""

_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def numbers_in(text: str) -> set[str]:
    """Numbers as written, normalised: '₹1,234.50' -> '1234.5', '20' -> '20', '20.0' -> '20'."""
    out = set()
    for raw in _NUMBER.findall(text or ""):
        value = raw.replace(",", "")
        if "." in value:
            value = value.rstrip("0").rstrip(".")
        out.add(value)
    return out


def material_text(headline: str, findings: list[dict], expectation: dict, review: dict) -> str:
    return json.dumps({
        "headline": headline,
        "findings": [{"side": f["side"], "text": f["text"]} for f in findings],
        "expectation": expectation["text"],
        "review": f"Do not revisit before {review['until_text']} unless {review['trigger']}.",
    }, ensure_ascii=False, indent=2)


def build_prompt(headline: str, findings: list[dict], expectation: dict, review: dict) -> tuple[str, str]:
    """(system prompt, user prompt)."""
    material = material_text(headline, findings, expectation, review)
    return SYSTEM_PROMPT, f"The decision:\n{material}\n\nWrite the narrative."


def narrate(headline: str, findings: list[dict], expectation: dict, review: dict) -> str | None:
    """The LLM's narrative, or None when the call fails or the reply invents a number."""
    system, user = build_prompt(headline, findings, expectation, review)
    result = call_llm(system, user)
    text = result.get("narrative") if isinstance(result, dict) else None
    if not isinstance(text, str) or not text.strip() or "error" in result:
        return None
    allowed = numbers_in(material_text(headline, findings, expectation, review))
    if not numbers_in(text) <= allowed:
        return None  # it introduced a number that is not in the findings
    return text.strip()
