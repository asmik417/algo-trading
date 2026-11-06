"""Stock endpoints for Explore: the searchable NSE universe, one stock's detail, on-demand analysis and evidence packs.
Thin router: logic lives in services/explore_service.py, suggestion_service.py and evidence_service.py.
"""
from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.brain import EvidencePack
from app.schemas.stock import StockDetail, StocksResponse
from app.schemas.suggestion import SuggestionDetail
from app.services import evidence_service, explore_service, suggestion_service

router = APIRouter(prefix="/stocks", tags=["stocks"])


@router.get("", response_model=StocksResponse)
def list_stocks(search: str = "", sort: str = "change_1m_pct", order: str = "desc",
                limit: int = Query(50, ge=1, le=explore_service.MAX_LIMIT), offset: int = Query(0, ge=0)):
    return explore_service.list_stocks(search, sort, order, limit, offset)


@router.get("/{symbol}", response_model=StockDetail)
def stock_detail(symbol: str):
    return explore_service.stock_detail(symbol)


@router.post("/{symbol}/analyze", response_model=SuggestionDetail)
def analyze(symbol: str, profile_id: int = Query(...), db: Session = Depends(get_db)):
    return suggestion_service.analyze_symbol(db, symbol, profile_id)


@router.get("/{symbol}/evidence", response_model=EvidencePack)
def evidence(symbol: str, day: date | None = None, db: Session = Depends(get_db)):
    return evidence_service.get(db, symbol, day)


@router.post("/{symbol}/evidence", response_model=EvidencePack, status_code=status.HTTP_201_CREATED)
def build_evidence(symbol: str, db: Session = Depends(get_db)):
    return evidence_service.build_now(db, symbol)
