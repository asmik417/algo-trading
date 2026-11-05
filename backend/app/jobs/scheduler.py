"""APScheduler setup: the daily update runs Mon-Fri at DAILY_JOB_HOUR:DAILY_JOB_MINUTE Asia/Kolkata inside the API.
Also answers "when is the next run" for GET /jobs/status, even when the scheduler is switched off.
"""
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.core.logging import get_logger
from app.jobs import daily_update

log = get_logger(__name__)

JOB_ID = "daily_update"
_scheduler: BackgroundScheduler | None = None


def trigger() -> CronTrigger:
    return CronTrigger(day_of_week="mon-fri", hour=settings.DAILY_JOB_HOUR, minute=settings.DAILY_JOB_MINUTE,
                       timezone=settings.TZ)


def _run_job() -> None:
    try:
        if daily_update.run_daily_update() is None:
            log.info("Scheduled daily update skipped: already running")
    except Exception:
        log.exception("Scheduled daily update failed")


def start() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(timezone=settings.TZ)
    _scheduler.add_job(_run_job, trigger(), id=JOB_ID, coalesce=True, max_instances=1, misfire_grace_time=3600)
    _scheduler.start()
    log.info("Scheduler started; next daily update at %s", next_run_iso())


def shutdown() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def next_run_iso() -> str | None:
    if _scheduler is not None and (job := _scheduler.get_job(JOB_ID)) is not None and job.next_run_time:
        when = job.next_run_time
    else:
        when = trigger().get_next_fire_time(None, datetime.now(timezone.utc))
    if when is None:
        return None
    return when.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
