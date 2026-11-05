import json
from app.engine.data.fetcher import fetch_fundamentals
from app.engine.agents.base_agent import call_llm
from app.engine.utils.logger import get_logger

log = get_logger(__name__)

SYSTEM_PROMPT = """You are a seasoned fundamental analyst covering Indian equities on NSE/BSE.
You evaluate companies based on valuation, growth, profitability, and balance sheet strength.
Always respond with valid JSON only. Context: Indian market, so benchmarks like PE should be relative
to sector averages in India. Be data-driven — no signal if data is missing."""

def analyze(symbol: str) -> dict:
    fundamentals = fetch_fundamentals(symbol)

    user_prompt = f"""Analyze the fundamental data for {symbol} (NSE listed company).

Fundamental Data:
{json.dumps(fundamentals, indent=2)}

Based on this data, assess if this stock is fundamentally attractive for a swing trade (3-15 days) or short-term investment.

Return JSON with exactly these fields:
{{
  "signal": "BUY" | "SELL" | "NEUTRAL",
  "confidence": <integer 1-5, where 5=very high conviction>,
  "valuation": "UNDERVALUED" | "FAIRLY_VALUED" | "OVERVALUED",
  "growth_outlook": "STRONG" | "MODERATE" | "WEAK" | "UNKNOWN",
  "reasoning": "<2-3 sentences on valuation and fundamentals>",
  "red_flags": ["<any concerning metrics>"],
  "positives": ["<key strengths>"]
}}

If data is too sparse (many nulls), set confidence to 1 and signal to NEUTRAL."""

    result = call_llm(SYSTEM_PROMPT, user_prompt)
    result["symbol"] = symbol
    result["agent"] = "fundamental"
    result["raw_data"] = fundamentals
    return result
