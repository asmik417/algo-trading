import json
from app.engine.data.fetcher import fetch_price_history
from app.engine.data.indicators import compute_indicators
from app.engine.agents.base_agent import call_llm
from app.engine.utils.logger import get_logger
from app.engine import config

log = get_logger(__name__)

SYSTEM_PROMPT = """You are a veteran technical analyst specializing in Indian equity markets (NSE/BSE).
You analyze chart indicators and price action to generate precise trading signals.
Always respond with valid JSON only. Be conservative — only signal BUY or SELL when conviction is high.
Your analysis should consider the Indian market context (FII/DII flows, Nifty correlation)."""

def analyze(symbol: str) -> dict:
    df = fetch_price_history(symbol, period=config.DATA_PERIOD, interval=config.DATA_INTERVAL)
    if df is None or df.empty:
        return {"symbol": symbol, "error": "No price data", "signal": "NEUTRAL", "confidence": 0}

    try:
        ind = compute_indicators(df)
    except Exception as e:
        return {"symbol": symbol, "error": f"Indicator error: {e}", "signal": "NEUTRAL", "confidence": 0}

    user_prompt = f"""Analyze this technical data for {symbol} (NSE) and give a trading signal.

Technical Indicators:
{json.dumps(ind, indent=2)}

Return JSON with exactly these fields:
{{
  "signal": "BUY" | "SELL" | "NEUTRAL",
  "confidence": <integer 1-5, where 5=very high>,
  "entry_aggressive": <float, entry price for immediate entry at current/near price>,
  "entry_optimal": <float, ideal pullback entry for best risk-reward>,
  "entry_conservative": <float, deeper pullback entry if market dips more>,
  "target_price": <float, realistic price target to exit>,
  "stop_loss": <float, stop-loss price to cut losses>,
  "predicted_days": <integer, expected holding period in trading days>,
  "reasoning": "<2-3 sentences explaining the signal based on indicators>",
  "key_levels": {{
    "support": <float>,
    "resistance": <float>
  }}
}}"""

    result = call_llm(SYSTEM_PROMPT, user_prompt)
    result["symbol"] = symbol
    result["agent"] = "technical"
    result["indicators"] = ind
    return result
