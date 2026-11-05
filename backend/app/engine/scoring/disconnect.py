"""Fundamental-Price Disconnect — the core idea behind this whole feature.

Detects "business performance improved significantly, but the stock hasn't
fully reacted yet" vs "business improved AND the market has already repriced
it." Not an intrinsic-value estimate — a measurable relative signal: how big
was the fundamental improvement vs. how much has the price already moved.

Revenue +50% / Profit +200% / 3M price return +5%  -> strong disconnect.
Revenue +50% / Profit +200% / 3M price return +150% -> weak disconnect (already priced in).
"""
from dataclasses import dataclass

from app.engine.scoring.common import scale


@dataclass
class DisconnectResult:
    available: bool
    label: str          # "Strong" | "Moderate" | "Weak" | "Priced In" | "Unavailable"
    score_0_1: float | None   # 0..1, higher = stronger disconnect (more unpriced improvement)
    fundamental_growth_pct: float | None
    price_return_3m_pct: float | None


def compute(fundamental_growth_pct: float | None, price_return_3m_pct: float | None) -> DisconnectResult:
    if fundamental_growth_pct is None or price_return_3m_pct is None or fundamental_growth_pct <= 0:
        return DisconnectResult(False, "Unavailable", None, fundamental_growth_pct, price_return_3m_pct)

    # How much of the fundamental improvement looks "used up" by the price move already.
    ratio = price_return_3m_pct / fundamental_growth_pct
    relative_score = scale(ratio, 0, 1.2, reverse=True)

    # Even with a favorable ratio, a stock that has already run up a lot in
    # absolute terms is not "early" anymore.
    extension_damp = scale(price_return_3m_pct, 20, 150, reverse=True)

    combined = 0.6 * relative_score + 0.4 * extension_damp

    if combined >= 0.7:
        label = "Strong"
    elif combined >= 0.45:
        label = "Moderate"
    elif combined >= 0.2:
        label = "Weak"
    else:
        label = "Priced In"

    return DisconnectResult(True, label, combined, fundamental_growth_pct, price_return_3m_pct)
