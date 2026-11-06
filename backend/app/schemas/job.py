"""Response shapes for the daily monitoring job: start acknowledgement and status.
Mirrors the Jobs section of docs/API_CONTRACT.md.
"""
from typing import Literal

from app.schemas.common import ApiModel, IsoDate


class JobStarted(ApiModel):
    started: bool
    reason: str | None = None


class JobSummary(ApiModel):
    marked: int
    closed_target: int
    closed_stop: int
    marked_due: int


class SourceStatus(ApiModel):
    source: str
    day: str
    status: Literal["ok", "empty", "failed"]
    records: int
    error: str | None


class BrainStatus(ApiModel):
    running: bool
    last_day: str | None
    sources: list[SourceStatus]
    packs_built: int
    views_built: int
    views_failed: int


class NightlyBrainBody(ApiModel):
    day: IsoDate | None = None


class NightlyBrainStarted(ApiModel):
    job_id: int


class JobStatus(ApiModel):
    running: bool
    last_daily_update: str | None
    last_trading_day: str | None
    next_scheduled: str | None
    last_summary: JobSummary | None
    brain: BrainStatus | None
