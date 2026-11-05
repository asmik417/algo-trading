"""Stock endpoints for Explore: the searchable NSE universe, one stock's detail, and on-demand analysis.
Thin router: logic lives in services/explore_service.py and services/suggestion_service.py.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.stock import StockDetail, StocksResponse
from app.schemas.suggestion import SuggestionDetail
from app.services import explore_service, suggestion_service

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
