"""In-memory live status of algo runs (phase, done/total, current symbol), guarded by one lock.
Enforces one active full run per profile; the database keeps the durable status and counts.
"""
import threading

_lock = threading.Lock()
_runs: dict[int, dict] = {}         # run_id -> progress + status
_active: dict[int, int] = {}        # profile_id -> run_id while queued/running


def start(run_id: int, profile_id: int, exclusive: bool = True) -> int | None:
    """Register a queued run. Exclusive (full) runs: returns the already-active run_id for this profile
    instead, if any. Watchlist runs are not exclusive: they never block, and are never blocked."""
    with _lock:
        if exclusive:
            existing = _active.get(profile_id)
            if existing is not None:
                return existing
            _active[profile_id] = run_id
        _runs[run_id] = {"profile_id": profile_id, "status": "queued", "phase": "panel",
                         "done": 0, "total": 0, "current_symbol": None}
        return None


def active_run(profile_id: int) -> int | None:
    with _lock:
        return _active.get(profile_id)


def update(run_id: int, **fields) -> None:
    with _lock:
        if run_id in _runs:
            _runs[run_id].update(fields)


def finish(run_id: int, status: str) -> None:
    with _lock:
        entry = _runs.get(run_id)
        if entry is None:
            return
        entry["status"] = status
        entry["current_symbol"] = None
        if status == "done":
            entry["phase"] = "done"
        if _active.get(entry["profile_id"]) == run_id:
            del _active[entry["profile_id"]]


def get(run_id: int) -> dict | None:
    with _lock:
        entry = _runs.get(run_id)
        return dict(entry) if entry else None


def clear() -> None:
    """Tests only."""
    with _lock:
        _runs.clear()
        _active.clear()
