"""Backtest endpoints: start one (background, one at a time), list, poll, results, delete.
Thin router: everything lives in services/backtest_service.py.
"""
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.backtest import Backtest, BacktestBody, BacktestResults
from app.services import backtest_service

router = APIRouter(prefix="/backtests", tags=["backtests"])


@router.post("", response_model=Backtest, status_code=status.HTTP_202_ACCEPTED,
             responses={409: {"description": 'Another backtest is queued or running: {"detail", "backtest_id"}'}})
def start_backtest(body: BacktestBody, db: Session = Depends(get_db)):
    bt = backtest_service.create(db, body.profile_id, body.start_date, body.end_date, body.frequency, body.entry_rule,
                                 body.fundamentals_mode, body.cost_pct, body.capital_per_trade)
    # Not refreshed: the 202 reply is the backtest as queued, even if its thread has already started.
    return backtest_service.to_schema(bt)


@router.get("", response_model=list[Backtest])
def list_backtests(profile_id: int | None = None, limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    return [backtest_service.to_schema(b) for b in backtest_service.list_backtests(db, profile_id, limit)]


@router.get("/{backtest_id}", response_model=Backtest)
def get_backtest(backtest_id: int, db: Session = Depends(get_db)):
    return backtest_service.to_schema(backtest_service.get(db, backtest_id))


@router.get("/{backtest_id}/results", response_model=BacktestResults)
def backtest_results(backtest_id: int, db: Session = Depends(get_db)):
    return backtest_service.results(db, backtest_id)


@router.delete("/{backtest_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_backtest(backtest_id: int, db: Session = Depends(get_db)):
    backtest_service.delete(db, backtest_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
