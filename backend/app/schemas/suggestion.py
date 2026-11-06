"""Response shapes for suggestions and the stock dialog (reasons, plan, score breakdown, chart, filters).
Mirrors the Suggestions section of docs/API_CONTRACT.md; also reused by /stocks/{symbol}/analyze.
"""
from typing import Literal

from app.schemas.common import ApiModel
from app.schemas.run import Run

SuggestionSource = Literal["run", "explore", "watchlist"]
Overall = Literal["buy", "watch", "avoid"]
Trend = Literal["uptrend", "downtrend", "sideways"]


class VerdictRules(ApiModel):
    passed: int
    total: int
    failures: list[str]


class VerdictChart(ApiModel):
    trend: Trend
    label: str
    points: list[str]


class Verdict(ApiModel):
    overall: Overall
    rules: VerdictRules
    chart: VerdictChart
    reason: str


Direction = Literal["up", "down", "sideways"]


class Finding(ApiModel):
    side: Literal["for", "against"]
    text: str


class Expectation(ApiModel):
    direction: Direction
    level: float | None
    by_date: str
    text: str


class ReviewRule(ApiModel):
    until: str
    trigger: str


class Confidence(ApiModel):
    signal_win_rate_pct: float | None
    trades: int | None
    backtest_id: int | None


class Decision(ApiModel):
    overall: Overall
    headline: str
    findings: list[Finding]
    expectation: Expectation
    review: ReviewRule
    confidence: Confidence
    narrative: str


class SuggestionSummary(ApiModel):
    id: int
    source: SuggestionSource
    verdict: Verdict
    symbol: str
    rank: int | None
    score: float
    stage: str
    signal: str
    price: float
    entry_optimal: float
    stop_loss: float
    target: float
    risk_reward: float
    horizon_days: int
    planned_exit_date: str
    market_cap_bucket: str
    sector: str | None
    profit_yoy_pct: float | None
    change_1m_pct: float | None
    change_3m_pct: float | None
    volume_ratio_20d: float | None
    is_tracked: bool
    position_id: int | None


class Reasons(ApiModel):
    why_flagged: str
    what_changed: str
    positives: list[str]
    risks: list[str]


class Plan(ApiModel):
    entry_aggressive: float
    entry_optimal: float
    entry_conservative: float
    stop_loss: float
    target: float
    risk_reward: float
    horizon_days: int
    planned_exit_date: str
    timing_note: str
    exit_note: str
    disclaimer: str


class PillarScore(ApiModel):
    key: str
    label: str
    score: float | None
    max: float
    weight: float
    available: bool
    details: dict[str, float | int | str | None]


class Indicators(ApiModel):
    rsi: float | None = None
    macd_signal: str | None = None
    ema_trend: str | None = None
    ema20: float | None = None
    ema50: float | None = None
    ema200: float | None = None
    atr: float | None = None
    bb_position: str | None = None
    volume_ratio: float | None = None


class Fundamentals(ApiModel):
    pe: float | None = None
    pb: float | None = None
    roe_pct: float | None = None
    debt_to_equity: float | None = None
    market_cap: float | None = None
    sector: str | None = None
    industry: str | None = None
    revenue_yoy_pct: float | None = None
    profit_yoy_pct: float | None = None
    eps_yoy_pct: float | None = None
    operating_margin_pct: float | None = None
    latest_ocf: float | None = None


class ChartData(ApiModel):
    dates: list[str]
    close: list[float]
    ema20: list[float | None]
    ema50: list[float | None]
    volume: list[float]


class FilterResult(ApiModel):
    passed: bool
    failures: list[str]


class SuggestionDetail(SuggestionSummary):
    trading_day: str
    reasons: Reasons
    plan: Plan
    score_breakdown: list[PillarScore]
    indicators: Indicators
    fundamentals: Fundamentals
    chart: ChartData
    filters: FilterResult
    decision: Decision


class SuggestionsResponse(ApiModel):
    run: Run | None
    items: list[SuggestionSummary]


class WatchlistHit(SuggestionSummary):
    """A symbol that was analysed (it may still have failed the filters)."""
    filters: FilterResult
    error: None
    decision: Decision


class WatchlistMiss(ApiModel):
    """A symbol that is unknown or could not be scored: no suggestion row, nothing to score or track."""
    id: None
    symbol: str
    error: str
    filters: None
    score: None
    signal: None
    stage: None
    price: None
    is_tracked: Literal[False]
    position_id: None


WatchlistItem = WatchlistHit | WatchlistMiss


class WatchlistResults(ApiModel):
    run: Run
    items: list[WatchlistItem]
