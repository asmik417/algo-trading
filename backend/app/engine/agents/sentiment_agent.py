import json
from app.engine.data.fetcher import fetch_news
from app.engine.agents.base_agent import call_llm
from app.engine.utils.logger import get_logger

log = get_logger(__name__)

SYSTEM_PROMPT = """You are a market sentiment analyst specializing in Indian equities.
You analyze news headlines and summaries to gauge short-term market sentiment for a stock.
Always respond with valid JSON only. Focus on news that would impact price in the next 1-15 days."""

def analyze(symbol: str) -> dict:
    news_items = fetch_news(symbol, limit=8)

    if not news_items:
        return {
            "symbol": symbol,
            "agent": "sentiment",
            "signal": "NEUTRAL",
            "confidence": 1,
            "sentiment_score": 50,
            "reasoning": "No recent news found.",
            "key_headlines": [],
        }

    news_text = "\n".join(
        f"- {n['title']} ({n['publisher']}): {n['summary'][:200]}"
        for n in news_items if n.get("title")
    )

    user_prompt = f"""Analyze the following recent news for {symbol} (NSE) and determine market sentiment.

Recent News:
{news_text}

Return JSON with exactly these fields:
{{
  "signal": "BUY" | "SELL" | "NEUTRAL",
  "confidence": <integer 1-5>,
  "sentiment_score": <integer 0-100, where 0=extremely bearish, 50=neutral, 100=extremely bullish>,
  "reasoning": "<2-3 sentences on overall sentiment and key catalysts>",
  "key_headlines": ["<top 3 most impactful headlines>"],
  "catalysts": {{
    "bullish": ["<positive catalysts>"],
    "bearish": ["<negative catalysts>"]
  }}
}}"""

    result = call_llm(SYSTEM_PROMPT, user_prompt)
    result["symbol"] = symbol
    result["agent"] = "sentiment"
    result["raw_news"] = news_items
    return result
