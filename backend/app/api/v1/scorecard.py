"""Scorecard endpoints: hit rates of logged rules verdicts and analyst views at 20/40/60 sessions, and the log itself.
Thin router: logic lives in services/scorecard_service.py.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.analyst import LoggedVerdict, Scorecard
from app.services import scorecard_service

router = APIRouter(prefix="/scorecard", tags=["scorecard"])


@router.get("", response_model=Scorecard)
def scorecard(profile_id: int | None = None, source: str = "both", horizon: int = 20, db: Session = Depends(get_db)):
    return scorecard_service.scorecard(db, profile_id, source, horizon)


@router.get("/verdicts", response_model=list[LoggedVerdict])
def logged_verdicts(profile_id: int | None = None, symbol: str | None = None,
                    limit: int = Query(50, ge=1, le=500), db: Session = Depends(get_db)):
    return scorecard_service.verdicts(db, profile_id, symbol, limit)
