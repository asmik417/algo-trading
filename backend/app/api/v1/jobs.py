"""Job endpoints: trigger the daily update in the background, and read its status and last summary.
Thin router: the job lives in app/jobs/.
"""
import json

from fastapi import APIRouter, Body, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.jobs import daily_update, nightly_brain, scheduler
from app.schemas.job import JobStarted, JobStatus, NightlyBrainBody, NightlyBrainStarted
from app.services.errors import Conflict

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/daily-update", response_model=JobStarted, response_model_exclude_none=True,
             status_code=status.HTTP_202_ACCEPTED,
             responses={200: {"model": JobStarted, "description": "Already running"}})
def trigger_daily_update(response: Response):
    if daily_update.start_in_background():
        return {"started": True}
    response.status_code = status.HTTP_200_OK
    return {"started": False, "reason": "already running"}


@router.post("/nightly-brain", response_model=NightlyBrainStarted, status_code=status.HTTP_202_ACCEPTED,
             responses={409: {"description": "Already running"}})
def trigger_nightly_brain(body: NightlyBrainBody | None = Body(default=None)):
    job_id = nightly_brain.start_in_background(body.day if body else None)
    if job_id is None:
        raise Conflict("The nightly brain job is already running.")
    return {"job_id": job_id}


@router.get("/status", response_model=JobStatus)
def job_status(db: Session = Depends(get_db)):
    meta = daily_update.read_meta()
    raw = meta.get("last_daily_summary")
    try:
        summary = json.loads(raw) if raw else None
    except ValueError:
        summary = None
    return {
        "running": daily_update.is_running(),
        "last_daily_update": meta.get("last_daily_update"),
        "last_trading_day": meta.get("last_trading_day"),
        "next_scheduled": scheduler.next_run_iso(),
        "last_summary": summary,
        "brain": nightly_brain.status(db),
    }
