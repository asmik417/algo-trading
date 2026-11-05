"""CLI: create the starter strategies and reset "Default – Balanced" to the current defaults.
Idempotent by name and never deletes. Usage from backend/: ../venv/bin/python scripts/seed_profiles.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select  # noqa: E402

from app.db.session import SessionLocal, init_db  # noqa: E402
from app.engine.params import DEFAULTS, ScreenParams  # noqa: E402
from app.models import Profile  # noqa: E402
from app.services import profile_service  # noqa: E402

OWNER = "Roshan"
DEVELOPER_SUGGESTED = "Developer suggested – Quality Momentum"
DEFAULT_BALANCED = "Default – Balanced"


def _weights(earnings, quality, early_price, volume, technical, valuation) -> dict:
    return {"w_earnings_acceleration": earnings, "w_fundamental_quality": quality, "w_early_price_position": early_price,
            "w_volume_accumulation": volume, "w_technical_setup": technical, "w_valuation": valuation}


STRATEGIES = [
    (DEVELOPER_SUGGESTED, {}),  # = DEFAULTS
    ("Conservative – Large Caps", {
        "allowed_caps": ["Large Cap"], "min_roe_pct": 18, "max_pe": 40, "min_profit_growth_pct": 15,
        "rsi_min": 45, "rsi_max": 65, "horizon": "Long (3-6 months)", **_weights(20, 30, 10, 10, 15, 15),
    }),
    ("Aggressive – Breakouts", {
        "min_roe_pct": 10, "min_profit_growth_pct": 25, "rsi_min": 50, "rsi_max": 80, "max_3m_runup_pct": 100,
        "min_volume_ratio": 1.5, "horizon": "Short (2-6 weeks)", **_weights(25, 10, 5, 20, 30, 10),
    }),
]


def main() -> int:
    init_db()
    with SessionLocal() as db:
        for name, params in STRATEGIES:
            existing = db.scalar(select(Profile).where(Profile.name == name))
            if existing is not None:
                print(f"skip    {existing.id:>3}  {name} (exists)")
                continue
            p = profile_service.create_profile(db, name, OWNER, params)
            print(f"created {p.id:>3}  {name}  —  {profile_service.params_of(p).summary()}")
            if name == DEVELOPER_SUGGESTED:
                profile_service.activate_profile(db, p.id)
                print(f"active  {p.id:>3}  {name}")

        default = db.scalar(select(Profile).where(Profile.name == DEFAULT_BALANCED))
        if default is not None:
            if profile_service.params_of(default).to_dict() == DEFAULTS:
                print(f"skip    {default.id:>3}  {DEFAULT_BALANCED} (already on current defaults)")
            else:
                # Replace (not merge) so every key, including ones added later, is the current default.
                default.params_json = ScreenParams.from_dict(dict(DEFAULTS)).to_json()
                db.commit()
                print(f"updated {default.id:>3}  {DEFAULT_BALANCED} -> current defaults")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
