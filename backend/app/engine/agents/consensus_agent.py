import json
from app.engine.agents.base_agent import call_llm
from app.engine.utils.logger import get_logger

log = get_logger(__name__)

SYSTEM_PROMPT = """You are a chief investment officer synthesizing multiple analyst reports.
Your job is to find consensus across independent analyses and make a final, risk-adjusted recommendation.
Only recommend action when there is meaningful agreement. Always respond with valid JSON only."""

SIGNAL_SCORE = {"BUY": 1, "NEUTRAL": 0, "SELL": -1}


def build_consensus(symbol: str, technical: dict, fundamental: dict, sentiment: dict) -> dict:
    agents = [technical, fundamental, sentiment]

    # Count signals
    signals = [a.get("signal", "NEUTRAL") for a in agents]
    confidences = [a.get("confidence", 1) for a in agents]

    buy_votes = signals.count("BUY")
    sell_votes = signals.count("SELL")
    neutral_votes = signals.count("NEUTRAL")

    # Weighted score: sum of (signal_score × confidence) normalized to 0-100
    raw_score = sum(SIGNAL_SCORE.get(s, 0) * c for s, c in zip(signals, confidences))
    max_possible = sum(confidences)
    consensus_score = int(((raw_score / max_possible) + 1) / 2 * 100) if max_possible > 0 else 50

    agent_summary = {
        "technical": {
            "signal": technical.get("signal", "NEUTRAL"),
            "confidence": technical.get("confidence", 0),
            "reasoning": technical.get("reasoning", ""),
            "entry_aggressive": technical.get("entry_aggressive"),
            "entry_optimal": technical.get("entry_optimal"),
            "entry_conservative": technical.get("entry_conservative"),
            "target": technical.get("target_price"),
            "stop_loss": technical.get("stop_loss"),
        },
        "fundamental": {
            "signal": fundamental.get("signal", "NEUTRAL"),
            "confidence": fundamental.get("confidence", 0),
            "reasoning": fundamental.get("reasoning", ""),
            "valuation": fundamental.get("valuation", ""),
        },
        "sentiment": {
            "signal": sentiment.get("signal", "NEUTRAL"),
            "confidence": sentiment.get("confidence", 0),
            "reasoning": sentiment.get("reasoning", ""),
            "sentiment_score": sentiment.get("sentiment_score", 50),
        },
    }

    user_prompt = f"""Synthesize these three independent analyses for {symbol} and make a final recommendation.

Agent Reports:
{json.dumps(agent_summary, indent=2)}

Vote Summary: BUY={buy_votes}, SELL={sell_votes}, NEUTRAL={neutral_votes}
Weighted Consensus Score: {consensus_score}/100 (>60 = bullish, <40 = bearish)

Return JSON with exactly these fields:
{{
  "final_signal": "BUY" | "SELL" | "NEUTRAL",
  "consensus_score": {consensus_score},
  "agreement_level": "STRONG" | "MODERATE" | "WEAK" | "CONFLICTED",
  "action_recommended": <true if >=2 agents agree and confidence is meaningful, else false>,
  "entry_strategy": "<when and how to enter — specific price level or condition>",
  "exit_strategy": "<target and stop-loss with rationale>",
  "predicted_timeframe": "<e.g. 3-7 trading days>",
  "overall_reasoning": "<3-4 sentences synthesizing all three views>",
  "watch_for": "<key risk or catalyst to monitor>"
}}"""

    result = call_llm(SYSTEM_PROMPT, user_prompt)
    result["symbol"] = symbol
    result["agent"] = "consensus"
    result["vote_breakdown"] = {"BUY": buy_votes, "SELL": sell_votes, "NEUTRAL": neutral_votes}
    result["agent_details"] = agent_summary
    # Ensure consensus_score is in final result even if LLM overwrites
    result["consensus_score"] = result.get("consensus_score", consensus_score)
    return result
