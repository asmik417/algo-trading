"""GET /health: is the API up, can it reach the DB, and which trading day does it know about.
Must stay fast and offline, so it never triggers a bhavcopy download.
"""
from fastapi import APIRouter
from sqlalchemy import text

from app.db.session import engine
from app.schemas.health import Health
from app.services import market_data

router = APIRouter(tags=["health"])


@router.get("/health", response_model=Health)
def health() -> dict:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"
    return {"status": "ok", "trading_day": market_data.known_trading_day(), "db": db_status}
