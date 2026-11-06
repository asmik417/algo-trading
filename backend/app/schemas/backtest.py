"""Request and response shapes for backtests (the time machine).
Mirrors the Backtests section of docs/API_CONTRACT.md.
"""
from typing import Any, Literal

from app.schemas.common import ApiModel
from app.schemas.run import RunProgress, RunStatus

ScanFrequency = Literal["weekly", "daily"]
EntryRule = Literal["next_close", "optimal_limit"]
FundamentalsMode = Literal["point_in_time", "technical_only"]
BacktestExit = Literal["target_hit", "stop_hit", "horizon_closed", "open"]


class BacktestBody(ApiModel):
    profile_id: int
    start_date: str
    end_date: str
    frequency: ScanFrequency = "weekly"
    entry_rule: EntryRule = "next_close"
    fundamentals_mode: FundamentalsMode = "point_in_time"
    cost_pct: float = 0.3
    capital_per_trade: float | None = None  # default: the profile's paper capital


class BacktestExits(ApiModel):
    target_hit: int
    stop_hit: int
    horizon_closed: int
    open: int


class BacktestSummary(ApiModel):
    trades: int
    closed: int
    wins: int
    losses: int
    open_at_end: int
    skipped_repeat: int
    skipped_no_fill: int
    win_rate_pct: float | None
    avg_win_pct: float | None
    avg_loss_pct: float | None
    avg_pnl_pct: float | None
    expectancy_r: float | None
    profit_factor: float | None
    total_pnl: float
    max_drawdown_pct: float | None
    avg_days_held: float | None
    nifty_avg_pct: float | None
    exits: BacktestExits


class Backtest(ApiModel):
    id: int
    profile_id: int
    profile_name: str
    status: RunStatus
    start_date: str
    end_date: str
    frequency: ScanFrequency
    entry_rule: EntryRule
    fundamentals_mode: FundamentalsMode
    cost_pct: float
    capital_per_trade: float
    params: dict[str, Any]
    progress: RunProgress
    scan_count: int | None
    summary: BacktestSummary | None
    caveats: list[str]
    error: str | None
    started_at: str | None
    finished_at: str | None
    created_at: str


class BacktestBreakdownRow(ApiModel):
    key: str
    trades: int
    win_rate_pct: float | None
    avg_pnl_pct: float | None
    total_pnl: float


class BacktestLossPattern(ApiModel):
    key: str
    label: str
    count: int
    share_pct: float


class BacktestTrade(ApiModel):
    id: int
    symbol: str
    scan_date: str
    entry_date: str
    entry_price: float
    qty: int
    invested: float
    stop_loss: float
    target: float
    planned_exit_date: str
    signal: str
    stage: str
    score: float
    market_cap_bucket: str
    sector: str | None
    exit_date: str | None
    exit_price: float | None
    exit_reason: BacktestExit
    pnl: float
    pnl_pct: float
    r_multiple: float | None
    days_held: int
    mfe_pct: float | None
    mae_pct: float | None
    nifty_pct: float | None
    tags: list[str]


class EquityPoint(ApiModel):
    date: str
    pnl: float


class BacktestResults(ApiModel):
    backtest: Backtest
    by_signal: list[BacktestBreakdownRow]
    by_stage: list[BacktestBreakdownRow]
    by_market_cap: list[BacktestBreakdownRow]
    by_sector: list[BacktestBreakdownRow]
    by_month: list[BacktestBreakdownRow]
    loss_patterns: list[BacktestLossPattern]
    equity_curve: list[EquityPoint]
    trades: list[BacktestTrade]
