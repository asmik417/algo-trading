"""Response shapes for the analyst view and the scorecard (docs/API_CONTRACT.md -> Analyst view, Verdict log and
scorecard). Kept apart from schemas/suggestion.py, which embeds AnalystView in SuggestionDetail and WatchlistHit.
"""
from typing import Literal

from app.schemas.common import ApiModel

AnalystAction = Literal["buy", "watch", "avoid", "add", "hold", "trim", "exit"]
AnalystConfidence = Literal["low", "medium", "high"]
CallDirection = Literal["up", "down", "sideways"]
VerdictSource = Literal["rules", "analyst"]


class AnalystTest(ApiModel):
    claim: str
    evidence: Literal["present", "absent", "unknown"]
    note: str


class AnalystView(ApiModel):
    id: int
    symbol: str
    day: str
    profile_id: int
    observations: list[str]
    anomalies: list[str]
    bull_case: str
    bear_case: str
    tests: list[AnalystTest]
    action: AnalystAction
    direction: CallDirection
    horizon_sessions: Literal[20]
    confidence: AnalystConfidence
    trigger: str
    want_to_know: str
    agrees_with_rules: bool | None
    audited: bool
    audit_notes: list[str]
    model: str
    created_at: str


class AnalystQueued(ApiModel):
    status: Literal["queued"]


class VerdictMark(ApiModel):
    sessions: Literal[20, 40, 60]
    date: str
    close: float
    change_pct: float
    right: bool


class LoggedVerdict(ApiModel):
    id: int
    symbol: str
    day: str
    source: VerdictSource
    profile_id: int
    action: AnalystAction
    direction: CallDirection
    level: float | None
    close: float
    signal: str | None
    marks: list[VerdictMark]


class ScorecardRow(ApiModel):
    key: str
    verdicts: int
    marked: int
    right: int
    hit_rate_pct: float | None
    avg_change_pct: float | None


class Scorecard(ApiModel):
    profile_id: int
    source: Literal["rules", "analyst", "both"]
    horizon: Literal[20, 40, 60]
    total: ScorecardRow
    by_source: list[ScorecardRow]
    by_action: list[ScorecardRow]
    by_signal: list[ScorecardRow]
    by_month: list[ScorecardRow]
    worst: list[LoggedVerdict]
