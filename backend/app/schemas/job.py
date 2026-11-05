"""Response shapes for the daily monitoring job: start acknowledgement and status.
Mirrors the Jobs section of docs/API_CONTRACT.md.
"""
from app.schemas.common import ApiModel


class JobStarted(ApiModel):
    started: bool
    reason: str | None = None


class JobSummary(ApiModel):
    marked: int
    closed_target: int
    closed_stop: int
    marked_due: int


class JobStatus(ApiModel):
    running: bool
    last_daily_update: str | None
    last_trading_day: str | None
    next_scheduled: str | None
    last_summary: JobSummary | None
