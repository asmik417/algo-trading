"""Step 10: the daily job — marks positions for the latest day, records app_meta, never runs twice at once;
the jobs endpoints and the scheduler's next run time. Synthetic prices; the lock file lives in tmp.
"""
import threading

from app.jobs import daily_update, scheduler
from app.services import market_data
from tests.test_tracker import _open, world  # noqa: F401  (fixture)


def _isolate(monkeypatch, tmp_path):
    monkeypatch.setattr(daily_update, "LOCK_PATH", str(tmp_path / "daily_update.lock"))
    monkeypatch.setattr(market_data, "refresh", market_data.panel_day)  # no NSE check in tests


def test_daily_update_marks_and_records(client, world, monkeypatch, tmp_path):  # noqa: F811
    _isolate(monkeypatch, tmp_path)
    pid = world["pid"]
    pos = _open(client, pid, world["suggest"](pid, "AAA")).json()["id"]
    world["set"]("2026-11-06", AAA={"2026-11-05": 105.0, "2026-11-06": 121.0})

    status = client.get("/api/v1/jobs/status").json()
    assert status["running"] is False and status["last_daily_update"] is None and status["last_summary"] is None

    assert daily_update.run_daily_update() == {"marked": 1, "closed_target": 1, "closed_stop": 0, "marked_due": 0}
    status = client.get("/api/v1/jobs/status").json()
    assert status["last_trading_day"] == "2026-11-06" and status["last_daily_update"].endswith("Z")
    assert status["last_summary"] == {"marked": 1, "closed_target": 1, "closed_stop": 0, "marked_due": 0}
    assert client.get(f"/api/v1/positions/{pos}").json()["close_reason"] == "target_hit"
    # idempotent for the same trading day
    assert daily_update.run_daily_update() == {"marked": 0, "closed_target": 0, "closed_stop": 0, "marked_due": 0}


def test_never_runs_twice(client, world, monkeypatch, tmp_path):  # noqa: F811
    _isolate(monkeypatch, tmp_path)
    entered, release = threading.Event(), threading.Event()
    real_mark_all = daily_update.tracker_service.mark_all

    def slow_mark_all(db, day):
        entered.set()
        release.wait(5)
        return real_mark_all(db, day)

    monkeypatch.setattr(daily_update.tracker_service, "mark_all", slow_mark_all)
    r = client.post("/api/v1/jobs/daily-update")
    assert r.status_code == 202 and r.json() == {"started": True}
    assert entered.wait(5)
    assert client.get("/api/v1/jobs/status").json()["running"] is True
    again = client.post("/api/v1/jobs/daily-update")
    assert again.status_code == 200 and again.json() == {"started": False, "reason": "already running"}
    assert daily_update.run_daily_update() is None
    # A second process would be blocked by the file lock even without the thread lock.
    fd = daily_update._try_file_lock()
    assert fd is None
    release.set()
    for _ in range(50):
        if not daily_update.is_running():
            break
        threading.Event().wait(0.1)
    assert client.get("/api/v1/jobs/status").json()["running"] is False


def test_next_scheduled_is_a_weekday_at_1830_ist():
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo

    nxt = scheduler.next_run_iso()
    when = datetime.fromisoformat(nxt.replace("Z", "+00:00")).astimezone(ZoneInfo("Asia/Kolkata"))
    assert (when.hour, when.minute) == (18, 30) and when.weekday() < 5
    assert when > datetime.now(timezone.utc)
