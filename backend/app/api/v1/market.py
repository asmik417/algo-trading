"""Market brief endpoints: the brief for a day (latest when no day is given) and the most recent briefs.
Thin router: logic lives in services/market_brief_service.py.
"""
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.brain import MarketBrief
from app.services import market_brief_service

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/brief", response_model=MarketBrief)
def market_brief(day: date | None = None, db: Session = Depends(get_db)):
    return market_brief_service.get(db, day)


@router.get("/briefs", response_model=list[MarketBrief])
def market_briefs(limit: int = Query(10, ge=1, le=60), db: Session = Depends(get_db)):
    return market_brief_service.recent(db, limit)
