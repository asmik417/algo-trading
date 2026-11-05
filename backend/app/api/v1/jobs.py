"""Job endpoints: trigger the daily update in the background, and read its status and last summary.
Thin router: the job lives in app/jobs/.
"""
import json

from fastapi import APIRouter, Response, status

from app.jobs import daily_update, scheduler
from app.schemas.job import JobStarted, JobStatus

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/daily-update", response_model=JobStarted, response_model_exclude_none=True,
             status_code=status.HTTP_202_ACCEPTED,
             responses={200: {"model": JobStarted, "description": "Already running"}})
def trigger_daily_update(response: Response):
    if daily_update.start_in_background():
        return {"started": True}
    response.status_code = status.HTTP_200_OK
    return {"started": False, "reason": "already running"}


@router.get("/status", response_model=JobStatus)
def job_status():
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
    }
