"""Request and response shapes for Loss Analysis: reason tags, reviews, pending losses and the tag summary.
Mirrors the Loss reviews section of docs/API_CONTRACT.md.
"""
from app.schemas.common import ApiModel
from app.schemas.position import CloseReason, Position


class ReviewTag(ApiModel):
    key: str
    label: str


class Review(ApiModel):
    id: int
    position_id: int
    symbol: str
    pnl: float
    pnl_pct: float
    closed_on: str
    close_reason: CloseReason
    reasons: list[str]
    mistakes: str
    lesson: str
    algo_change: str
    reviewed_on: str
    created_at: str


class ReviewBody(ApiModel):
    reasons: list[str]
    mistakes: str
    lesson: str
    algo_change: str


class LossesResponse(ApiModel):
    pending: list[Position]
    reviewed: list[Review]


class TagCount(ApiModel):
    key: str
    label: str
    count: int


class LossSummary(ApiModel):
    total_losses: int
    reviewed: int
    by_tag: list[TagCount]
    avg_loss_pct: float | None
