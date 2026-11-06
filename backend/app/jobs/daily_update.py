"""The nightly monitoring job: refresh the NSE panel, mark every open/due paper position and the scorecard's verdicts.
Never runs twice at once, across threads or processes (API scheduler, POST /jobs/daily-update, the CLI script).
"""
import fcntl
import json
import os
import threading

from app.core.clock import utc_now_iso
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.engine import config as engine_config
from app.models import AppMeta
from app.services import market_data, scorecard_service, tracker_service

log = get_logger(__name__)

LOCK_PATH = os.path.join(engine_config.BACKEND_DIR, "data", "daily_update.lock")
_thread_lock = threading.Lock()


def is_running() -> bool:
    if _thread_lock.locked():
        return True
    fd = _try_file_lock()
    if fd is None:
        return True
    _release_file_lock(fd)
    return False


def _try_file_lock() -> int | None:
    os.makedirs(os.path.dirname(LOCK_PATH), exist_ok=True)
    fd = os.open(LOCK_PATH, os.O_CREAT | os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except OSError:
        os.close(fd)
        return None


def _release_file_lock(fd: int) -> None:
    fcntl.flock(fd, fcntl.LOCK_UN)
    os.close(fd)


def _write_meta(values: dict[str, str]) -> None:
    with SessionLocal() as db:
        for key, value in values.items():
            db.merge(AppMeta(key=key, value=value))
        db.commit()


def read_meta() -> dict[str, str | None]:
    with SessionLocal() as db:
        return {m.key: m.value for m in db.query(AppMeta).all()}


def run_daily_update() -> dict | None:
    """Run the job now in this thread. Returns the summary, or None if another run holds the lock."""
    if not _thread_lock.acquire(blocking=False):
        return None
    fd = None
    try:
        fd = _try_file_lock()
        if fd is None:
            return None
        log.info("Daily update started")
        day = market_data.refresh()
        if not day:
            raise RuntimeError("No market data available; positions were not marked")
        with SessionLocal() as db:
            summary = tracker_service.mark_all(db, day)
            try:  # the scorecard: log new rules verdicts, mark logged ones that reached 20/40/60 sessions
                logged, marks = scorecard_service.log_rules_verdicts(db), scorecard_service.mark_all(db)
                log.info("Scorecard: %d verdicts logged, %d marks added", logged, marks)
            except Exception:
                db.rollback()
                log.exception("Scorecard marking failed; positions were still marked")
        _write_meta({"last_daily_update": utc_now_iso(), "last_trading_day": day,
                     "last_daily_summary": json.dumps(summary)})
        log.info("Daily update done for %s: %s", day, summary)
        return summary
    finally:
        if fd is not None:
            _release_file_lock(fd)
        _thread_lock.release()


def start_in_background() -> bool:
    """Kick the job off in a thread. False if it is already running."""
    if is_running():
        return False

    def _go():
        try:
            run_daily_update()
        except Exception:
            log.exception("Daily update failed")

    threading.Thread(target=_go, name="daily-update", daemon=True).start()
    return True
