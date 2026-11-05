"""Request and response shapes for the Tracker: paper positions, marks, events and per-profile stats.
Mirrors the Positions section of docs/API_CONTRACT.md.
"""
from typing import Literal

from pydantic import Field

from app.schemas.common import ApiModel, IsoDate
from app.schemas.suggestion import SuggestionSummary

PositionStatus = Literal["open", "due", "closed"]
CloseReason = Literal["target_hit", "stop_hit", "horizon_closed", "manual"]
EventType = Literal["open", "extend", "shorten", "due", "close", "note"]


class Position(ApiModel):
    id: int
    profile_id: int
    suggestion_id: int | None
    symbol: str
    opened_on: str
    entry_price: float
    qty: int
    invested: float
    capital: float
    cash_left: float
    target: float | None
    stop_loss: float | None
    original_exit_date: str
    planned_exit_date: str
    status: PositionStatus
    last_mark_date: str | None
    last_close: float | None
    current_value: float | None
    pnl: float | None
    pnl_pct: float | None
    days_held: int
    days_to_exit: int | None
    closed_on: str | None
    exit_price: float | None
    close_reason: CloseReason | None
    needs_review: bool
    stage: str | None
    signal: str | None


class Mark(ApiModel):
    mark_date: str
    close: float
    value: float
    pnl: float
    pnl_pct: float


class PositionEvent(ApiModel):
    id: int
    event_date: str
    event_type: EventType
    old_exit_date: str | None
    new_exit_date: str | None
    reason: str | None
    price: float | None
    created_at: str


class Benchmark(ApiModel):
    symbol: str
    change_pct_since_open: float


class PositionDetail(Position):
    marks: list[Mark]
    events: list[PositionEvent]
    suggestion: SuggestionSummary | None
    benchmark: Benchmark | None


class SymbolPnl(ApiModel):
    symbol: str
    pnl_pct: float


class ClosedBy(ApiModel):
    target_hit: int = 0
    stop_hit: int = 0
    horizon_closed: int = 0
    manual: int = 0


class ExtensionStats(ApiModel):
    count: int = 0
    helped: int = 0
    hurt: int = 0


class ProfileStats(ApiModel):
    open: int
    due: int
    closed: int
    wins: int
    losses: int
    win_rate_pct: float | None
    avg_pnl_pct: float | None
    avg_win_pct: float | None
    avg_loss_pct: float | None
    total_pnl: float       # all positions
    realised_pnl: float    # closed only
    unrealised_pnl: float  # open + due
    total_invested: float
    best: SymbolPnl | None
    worst: SymbolPnl | None
    closed_by: ClosedBy
    extensions: ExtensionStats
    pending_reviews: int


# ---- requests -------------------------------------------------------------

class CreatePositionBody(ApiModel):
    profile_id: int
    suggestion_id: int | None = None
    symbol: str | None = None
    capital: float | None = Field(default=None, gt=0)


class ChangeExitBody(ApiModel):
    new_exit_date: IsoDate
    reason: str


class ClosePositionBody(ApiModel):
    reason: str


class NoteBody(ApiModel):
    note: str
