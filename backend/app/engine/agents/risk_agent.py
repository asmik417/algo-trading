from app.engine import config
from app.engine.utils.logger import get_logger

log = get_logger(__name__)


def calculate_risk(consensus: dict, capital: float = config.DEFAULT_CAPITAL) -> dict:
    signal = consensus.get("final_signal", "NEUTRAL")
    action = consensus.get("action_recommended", False)
    agent_details = consensus.get("agent_details", {})
    technical = agent_details.get("technical", {})

    current_price = None
    target_price = technical.get("target")
    stop_loss_price = technical.get("stop_loss")

    # Try to get current price from indicators stored in technical agent output
    # (passed through from consensus agent_details)
    # We'll compute from target and stop_loss ratios

    if not action or signal == "NEUTRAL":
        return {
            "symbol": consensus.get("symbol"),
            "action": "SKIP",
            "reason": "No strong consensus — stay out or paper trade only.",
            "position_size_inr": 0,
            "shares": 0,
        }

    result = {
        "symbol": consensus.get("symbol"),
        "action": signal,
        "capital_inr": capital,
        "max_risk_inr": round(capital * config.MAX_RISK_PCT, 2),
    }

    if target_price and stop_loss_price and target_price != stop_loss_price:
        # Risk-reward ratio
        if signal == "BUY":
            risk_per_share = target_price - stop_loss_price
            reward_per_share = target_price - stop_loss_price
            # Correct: reward = target - entry (use stop_loss as proxy for entry)
            # More precisely use stop_loss as floor, target as ceiling
        else:
            risk_per_share = stop_loss_price - target_price
            reward_per_share = stop_loss_price - target_price

        rr_ratio = abs(reward_per_share / risk_per_share) if risk_per_share != 0 else 0

        # Position sizing: risk only MAX_RISK_PCT of capital
        if risk_per_share > 0:
            shares = int(result["max_risk_inr"] / abs(risk_per_share))
            position_cost = shares * stop_loss_price  # rough cost at stop level
        else:
            shares = 0
            position_cost = 0

        result.update({
            "target_price": round(target_price, 2),
            "stop_loss_price": round(stop_loss_price, 2),
            "risk_reward_ratio": round(rr_ratio, 2),
            "suggested_shares": max(shares, 0),
            "position_size_inr": round(position_cost, 2),
            "note": f"With ₹{capital} capital, risk at most ₹{result['max_risk_inr']} (1%) per trade.",
        })
    else:
        result.update({
            "suggested_shares": 1,
            "position_size_inr": capital * 0.1,
            "note": "Target/stop-loss not precisely defined. Use manual levels. Keep position small.",
        })

    return result
