"""Single-user login: check the one username/password from .env, sign/verify the session cookie, and
rate-limit failed attempts per client IP (5 failures in 15 minutes -> blocked until the oldest one ages out).
"""
import secrets
import threading
import time
from collections import deque

from itsdangerous import BadSignature, URLSafeTimedSerializer

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)

_SALT = "session"

MAX_FAILURES = 5
FAILURE_WINDOW_S = 15 * 60
_failures: dict[str, deque[float]] = {}
_failures_lock = threading.Lock()


def _recent(ip: str, now: float) -> deque[float]:
    q = _failures.setdefault(ip, deque())
    while q and now - q[0] >= FAILURE_WINDOW_S:
        q.popleft()
    return q


def is_blocked(ip: str) -> bool:
    with _failures_lock:
        return len(_recent(ip, time.monotonic())) >= MAX_FAILURES


def record_failure(ip: str) -> None:
    with _failures_lock:
        now = time.monotonic()
        _recent(ip, now).append(now)
        # Keep memory bounded: drop clients whose failures have all aged out.
        for other in [k for k, q in _failures.items() if not q or now - q[-1] >= FAILURE_WINDOW_S]:
            del _failures[other]


def record_success(ip: str) -> None:
    with _failures_lock:
        _failures.pop(ip, None)


def reset_rate_limit() -> None:
    """Tests only."""
    with _failures_lock:
        _failures.clear()


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.SECRET_KEY, salt=_SALT)


def check_credentials(username: str, password: str) -> bool:
    """Constant-time comparison of both fields; always False when no login is configured."""
    if not settings.APP_USERNAME or not settings.APP_PASSWORD:
        log.warning("Login attempted but APP_USERNAME / APP_PASSWORD are not set in backend/.env")
        return False
    user_ok = secrets.compare_digest(username.encode(), settings.APP_USERNAME.encode())
    pass_ok = secrets.compare_digest(password.encode(), settings.APP_PASSWORD.encode())
    return user_ok and pass_ok


def make_token(username: str) -> str:
    return _serializer().dumps({"u": username})


def read_token(token: str | None) -> str | None:
    """Username from a valid, unexpired cookie for the configured user, else None."""
    if not token:
        return None
    try:
        data = _serializer().loads(token, max_age=settings.SESSION_MAX_AGE)
    except BadSignature:  # also covers SignatureExpired
        return None
    username = data.get("u") if isinstance(data, dict) else None
    if not username or not settings.APP_USERNAME or not secrets.compare_digest(username, settings.APP_USERNAME):
        return None  # e.g. APP_USERNAME was changed: old cookies stop working
    return username
