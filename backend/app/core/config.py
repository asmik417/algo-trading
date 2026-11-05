"""API-level settings: URL prefix, CORS, database URL, the daily job schedule and single-user login.
Engine settings (thresholds, weights, cache dirs) stay in app.engine.config and are re-exported here.
"""
import logging
import os
import secrets

from pydantic import BaseModel, Field

from app.engine import config as engine_config


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    return int(raw) if raw.isdigit() else default


def _secret_key() -> str:
    key = os.getenv("SECRET_KEY", "").strip()
    if key:
        return key
    logging.getLogger(__name__).warning(
        "SECRET_KEY is not set in backend/.env; using a random key, so every restart logs everyone out.")
    return secrets.token_urlsafe(32)


class Settings(BaseModel):
    API_PREFIX: str = "/api/v1"
    CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:4820,http://127.0.0.1:4820").split(",") if o.strip()]
    )
    DATABASE_URL: str = engine_config.DATABASE_URL
    DAILY_JOB_HOUR: int = _env_int("DAILY_JOB_HOUR", 18)
    DAILY_JOB_MINUTE: int = _env_int("DAILY_JOB_MINUTE", 30)
    TZ: str = "Asia/Kolkata"
    # Tests set this to "0" so the background scheduler never starts under pytest.
    ENABLE_SCHEDULER: bool = os.getenv("ENABLE_SCHEDULER", "1") != "0"
    # Build the NSE panel in the background at startup so the first run is fast (tests set "0").
    WARM_PANEL: bool = os.getenv("WARM_PANEL", "1") != "0"
    # Single-user login (docs/API_CONTRACT.md -> Auth). Values come from backend/.env.
    APP_USERNAME: str = os.getenv("APP_USERNAME", "").strip()
    APP_PASSWORD: str = Field(default=os.getenv("APP_PASSWORD", ""), repr=False)
    SECRET_KEY: str = Field(default_factory=_secret_key, repr=False)
    SESSION_COOKIE: str = "session"
    SESSION_MAX_AGE: int = 30 * 24 * 3600  # 30 days, in seconds
    # Leave off for http://localhost; set COOKIE_SECURE=1 when served over HTTPS.
    COOKIE_SECURE: bool = os.getenv("COOKIE_SECURE", "0") == "1"


settings = Settings()
engine = engine_config  # re-export: `from app.core.config import engine` gives the engine's settings
