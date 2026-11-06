"""Run endpoints: full runs and watchlist runs (background), poll a run, watchlist results, list runs.
Thin router: the pipelines live in services/suggestion_service.py.
"""
from fastapi import APIRouter, Body, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.run import Run, StartRunBody, WatchlistRunBody
from app.schemas.suggestion import WatchlistResults
from app.services import suggestion_service

router = APIRouter(tags=["runs"])


@router.post("/profiles/{profile_id}/runs", response_model=Run, status_code=status.HTTP_202_ACCEPTED,
             responses={200: {"model": Run, "description": "A run for this profile is already active"}})
def start_run(profile_id: int, response: Response, body: StartRunBody | None = Body(default=None),
              db: Session = Depends(get_db)):
    run, created = suggestion_service.start_run(db, profile_id, force_refetch=bool(body and body.force_refetch))
    if not created:
        response.status_code = status.HTTP_200_OK
    return suggestion_service.run_to_schema(run)


@router.get("/runs/{run_id}", response_model=Run)
def get_run(run_id: int, db: Session = Depends(get_db)):
    return suggestion_service.run_to_schema(suggestion_service.get_run(db, run_id))


@router.get("/profiles/{profile_id}/runs", response_model=list[Run])
def list_runs(profile_id: int, limit: int = Query(10, ge=1, le=100), db: Session = Depends(get_db)):
    return [suggestion_service.run_to_schema(r) for r in suggestion_service.list_runs(db, profile_id, limit)]


@router.post("/profiles/{profile_id}/watchlist-runs", response_model=Run, status_code=status.HTTP_202_ACCEPTED)
def start_watchlist_run(profile_id: int, body: WatchlistRunBody, db: Session = Depends(get_db)):
    run = suggestion_service.start_watchlist_run(db, profile_id, symbols=body.symbols, list_id=body.list_id)
    return suggestion_service.run_to_schema(run)


@router.get("/profiles/{profile_id}/watchlist-runs", response_model=list[Run])
def list_watchlist_runs(profile_id: int, limit: int = Query(10, ge=1, le=100), list_id: int | None = None,
                        db: Session = Depends(get_db)):
    runs = suggestion_service.list_watchlist_runs(db, profile_id, limit, list_id)
    return [suggestion_service.run_to_schema(r) for r in runs]


@router.get("/runs/{run_id}/results", response_model=WatchlistResults)
def watchlist_results(run_id: int, db: Session = Depends(get_db)):
    return suggestion_service.watchlist_results(db, run_id)
