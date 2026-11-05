"""Request and response shapes for algo runs and their live progress.
Mirrors the Runs section of docs/API_CONTRACT.md.
"""
from typing import Literal

from app.schemas.common import ApiModel

RunStatus = Literal["queued", "running", "done", "failed"]
RunKind = Literal["full", "watchlist"]


class RunProgress(ApiModel):
    phase: str  # panel | prefilter | scoring | filtering | planning | saving | done
    done: int
    total: int
    current_symbol: str | None


class Run(ApiModel):
    id: int
    profile_id: int
    status: RunStatus
    kind: RunKind
    symbols: list[str] | None
    trading_day: str | None
    progress: RunProgress
    universe_size: int | None
    scored_size: int | None
    passed_size: int | None
    error: str | None
    started_at: str | None
    finished_at: str | None
    created_at: str


class StartRunBody(ApiModel):
    force_refetch: bool = False


class WatchlistRunBody(ApiModel):
    symbols: list[str]
