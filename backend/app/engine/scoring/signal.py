"""User-facing signal classification — the 5 states shown in the UI."""

SIGNALS = {
    "EARLY_SETUP": "🟢 Early Setup",
    "DEVELOPING": "🟡 Developing",
    "BREAKOUT_CONFIRMED": "🔵 Breakout Confirmed",
    "EXTENDED": "🟠 Extended",
    "WEAK": "🔴 Weak / Invalidated",
}


def classify(total_score: float | None, stage: str, technical_score_frac: float | None) -> str:
    if total_score is None or total_score < 40:
        return SIGNALS["WEAK"]

    weak_technical = technical_score_frac is not None and technical_score_frac < 0.25
    if weak_technical and total_score < 55:
        return SIGNALS["WEAK"]

    if stage == "Extended":
        return SIGNALS["EXTENDED"]

    if stage in ("Breakout", "Momentum") and total_score >= 60:
        return SIGNALS["BREAKOUT_CONFIRMED"]

    if stage in ("Fundamental Change", "Quiet Accumulation") and total_score >= 65:
        return SIGNALS["EARLY_SETUP"]

    if total_score >= 45:
        return SIGNALS["DEVELOPING"]

    return SIGNALS["WEAK"]
