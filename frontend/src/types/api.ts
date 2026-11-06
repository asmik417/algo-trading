// Copied verbatim from docs/API_CONTRACT.md: the Auth, Watchlist runs, Pick lists, Decision, Backtests and The brain
// snippets and the TypeScript types section. Do not edit by hand.

export interface LoginBody { username: string; password: string; }
export interface Me { username: string; }

// WatchlistRunBody: see "Pick lists" (list_id or symbols, exactly one)
export interface WatchlistHit extends SuggestionSummary { decision: Decision; analyst: AnalystView | null; filters: FilterResult; error: null; }
export interface WatchlistMiss { id: null; symbol: string; error: string; filters: null; score: null; signal: null; stage: null; price: null; is_tracked: false; position_id: null; }
export type WatchlistItem = WatchlistHit | WatchlistMiss;
export interface WatchlistResults { run: Run; items: WatchlistItem[]; }

export interface WatchlistRunBody { list_id?: number; symbols?: string[]; }   // exactly one

export type Direction = 'up' | 'down' | 'sideways';
export interface Finding { side: 'for' | 'against'; text: string; }           // text always carries its number, e.g. "Delivery % fell from 51% to 39% during the surge"
export interface Expectation { direction: Direction; level: number | null; by_date: string; text: string; }
export interface ReviewRule { until: string; trigger: string; }               // "do not revisit before <until> unless <trigger>"
export interface Confidence { signal_win_rate_pct: number | null; trades: number | null; backtest_id: number | null; }
export interface Decision { overall: Overall; headline: string; findings: Finding[]; expectation: Expectation; review: ReviewRule; confidence: Confidence; narrative: string; }

export type ScanFrequency = 'weekly' | 'daily';
export type EntryRule = 'next_close' | 'optimal_limit';
export type FundamentalsMode = 'point_in_time' | 'technical_only';
export type BacktestExit = CloseReason | 'open';
export interface BacktestBody { profile_id: number; start_date: string; end_date: string; frequency?: ScanFrequency; entry_rule?: EntryRule; fundamentals_mode?: FundamentalsMode; cost_pct?: number; capital_per_trade?: number; }
export interface BacktestSummary { trades: number; closed: number; wins: number; losses: number; open_at_end: number; skipped_repeat: number; skipped_no_fill: number; win_rate_pct: number | null; avg_win_pct: number | null; avg_loss_pct: number | null; avg_pnl_pct: number | null; expectancy_r: number | null; profit_factor: number | null; total_pnl: number; max_drawdown_pct: number | null; avg_days_held: number | null; nifty_avg_pct: number | null; exits: { target_hit: number; stop_hit: number; horizon_closed: number; open: number }; }
export interface Backtest { id: number; profile_id: number; profile_name: string; status: RunStatus; start_date: string; end_date: string; frequency: ScanFrequency; entry_rule: EntryRule; fundamentals_mode: FundamentalsMode; cost_pct: number; capital_per_trade: number; params: Record<string, unknown>; progress: RunProgress; scan_count: number | null; summary: BacktestSummary | null; caveats: string[]; error: string | null; started_at: string | null; finished_at: string | null; created_at: string; }
export interface BacktestBreakdownRow { key: string; trades: number; win_rate_pct: number | null; avg_pnl_pct: number | null; total_pnl: number; }
export interface BacktestLossPattern { key: string; label: string; count: number; share_pct: number; }
export interface BacktestTrade { id: number; symbol: string; scan_date: string; entry_date: string; entry_price: number; qty: number; invested: number; stop_loss: number; target: number; planned_exit_date: string; signal: string; stage: string; score: number; market_cap_bucket: string; sector: string | null; exit_date: string | null; exit_price: number | null; exit_reason: BacktestExit; pnl: number; pnl_pct: number; r_multiple: number | null; days_held: number; mfe_pct: number | null; mae_pct: number | null; nifty_pct: number | null; tags: string[]; }
export interface EquityPoint { date: string; pnl: number; }
export interface BacktestResults { backtest: Backtest; by_signal: BacktestBreakdownRow[]; by_stage: BacktestBreakdownRow[]; by_market_cap: BacktestBreakdownRow[]; by_sector: BacktestBreakdownRow[]; by_month: BacktestBreakdownRow[]; loss_patterns: BacktestLossPattern[]; equity_curve: EquityPoint[]; trades: BacktestTrade[]; }

export interface SourceStatus { source: string; day: string; status: 'ok' | 'empty' | 'failed'; records: number; error: string | null; }

// money in ₹ crore, eps in ₹, period = quarter-end date
export interface QuarterRow { period: string; filed_on: string | null; revenue: number | null; ebitda: number | null; net_profit: number | null; eps: number | null; margin_pct: number | null; }
export interface Ownership { as_of: string | null; promoter_pct: number | null; promoter_change_pct: number | null; fii_pct: number | null; dii_pct: number | null; public_pct: number | null; pledge_pct: number | null; }
export interface DealRow { date: string; kind: 'bulk' | 'block' | 'insider_buy' | 'insider_sell'; party: string; qty: number; price: number | null; }
export interface EventRow { date: string; kind: string; title: string; }
export interface Headline { date: string; title: string; source: string; url: string; }
export interface MarketContext { day: string; nifty_close: number | null; nifty_vs_ema50_pct: number | null; nifty_1w_pct: number | null; vix: number | null; advance_decline: number | null; fii_net_cr: number | null; dii_net_cr: number | null; sector_index: string | null; sector_1w_pct: number | null; sp500_1d_pct: number | null; crude_1w_pct: number | null; usdinr_1w_pct: number | null; }
export interface EvidencePack { symbol: string; day: string; price: { close: number; change_1w_pct: number | null; change_1m_pct: number | null; change_3m_pct: number | null; vs_nifty_1m_pct: number | null; vs_sector_1m_pct: number | null; dist_52w_high_pct: number | null; volume_ratio: number | null; delivery_pct_now: number | null; delivery_pct_prev: number | null; ema_trend: string | null; rsi: number | null; }; quarters: QuarterRow[]; ownership: Ownership | null; deals: DealRow[]; events: EventRow[]; headlines: Headline[]; market: MarketContext; rules_verdict: Verdict | null; plan: Plan | null; unavailable: string[]; }

export type AnalystConfidence = 'low' | 'medium' | 'high';
export type AnalystAction = 'buy' | 'watch' | 'avoid' | 'add' | 'hold' | 'trim' | 'exit';
export type AnalystRunResult = { status: 'queued' } | AnalystView;
export interface AnalystView { id: number; symbol: string; day: string; profile_id: number; observations: string[]; anomalies: string[]; bull_case: string; bear_case: string; tests: { claim: string; evidence: 'present' | 'absent' | 'unknown'; note: string }[]; action: AnalystAction; direction: Direction; horizon_sessions: 20; confidence: AnalystConfidence; trigger: string; want_to_know: string; agrees_with_rules: boolean | null; audited: boolean; audit_notes: string[]; model: string; created_at: string; }

export type Regime = 'risk_on' | 'neutral' | 'risk_off';
export interface MarketBrief { day: string; regime: Regime; audited: boolean; audit_notes: string[]; model: string; context: MarketContext; leaders: { index: string; change_1w_pct: number }[]; laggards: { index: string; change_1w_pct: number }[]; facts: string[]; paragraph: string; stance: string; created_at: string; }

export type VerdictSource = 'rules' | 'analyst';
export interface LoggedVerdict { id: number; symbol: string; day: string; source: VerdictSource; profile_id: number; action: AnalystAction; direction: Direction; level: number | null; close: number; signal: string | null; marks: { sessions: 20 | 40 | 60; date: string; close: number; change_pct: number; right: boolean }[]; }
export interface ScorecardRow { key: string; verdicts: number; marked: number; right: number; hit_rate_pct: number | null; avg_change_pct: number | null; }
export interface Scorecard { profile_id: number; source: VerdictSource | 'both'; horizon: 20 | 40 | 60; total: ScorecardRow; by_source: ScorecardRow[]; by_action: ScorecardRow[]; by_signal: ScorecardRow[]; by_month: ScorecardRow[]; worst: LoggedVerdict[]; }

export type RunStatus = 'queued' | 'running' | 'done' | 'failed';
export type RunKind = 'full' | 'watchlist';
export type Overall = 'buy' | 'watch' | 'avoid';
export type Trend = 'uptrend' | 'downtrend' | 'sideways';
export interface Verdict { overall: Overall; rules: { passed: number; total: number; failures: string[] }; chart: { trend: Trend; label: string; points: string[] }; reason: string; }
export type PositionStatus = 'open' | 'due' | 'closed';
export type CloseReason = 'target_hit' | 'stop_hit' | 'horizon_closed' | 'manual';
export type EventType = 'open' | 'extend' | 'shorten' | 'due' | 'close' | 'note';
export type FieldType = 'number' | 'int' | 'bool' | 'select' | 'multiselect';

export interface ParamField { key: string; label: string; type: FieldType; min?: number; max?: number; step?: number; options?: string[]; help?: string; }
export interface ParamSection { section: string; help?: string; fields: ParamField[]; }
export interface ParamSpec { defaults: Record<string, unknown>; horizons: string[]; cap_buckets: string[]; sections: ParamSection[]; }
export type Params = Record<string, number | boolean | string | string[]>;

export interface Profile { id: number; name: string; owner: string; is_active: boolean; params: Params; params_summary: string; created_at: string; updated_at: string; }

export interface PickList { id: number; name: string; symbols: string[]; created_at: string; updated_at: string; }
export interface CreatePickListBody { name: string; symbols: string[]; }
export interface UpdatePickListBody { name?: string; symbols?: string[]; }
export interface RunProgress { phase: string; done: number; total: number; current_symbol: string | null; }
export interface Run { id: number; profile_id: number; status: RunStatus; kind: RunKind; symbols: string[] | null; list_id: number | null; list_name: string | null; trading_day: string | null; progress: RunProgress; universe_size: number | null; scored_size: number | null; passed_size: number | null; error: string | null; started_at: string | null; finished_at: string | null; created_at: string; }

export type SuggestionSource = 'run' | 'explore' | 'watchlist';
export interface SuggestionSummary { id: number; source: SuggestionSource; verdict: Verdict; headline: string; symbol: string; rank: number | null; score: number; stage: string; signal: string; price: number; entry_optimal: number; stop_loss: number; target: number; risk_reward: number; horizon_days: number; planned_exit_date: string; market_cap_bucket: string; sector: string | null; profit_yoy_pct: number | null; change_1m_pct: number | null; change_3m_pct: number | null; volume_ratio_20d: number | null; is_tracked: boolean; position_id: number | null; }
export interface Reasons { why_flagged: string; what_changed: string; positives: string[]; risks: string[]; }
export interface Plan { entry_aggressive: number; entry_optimal: number; entry_conservative: number; stop_loss: number; target: number; risk_reward: number; horizon_days: number; planned_exit_date: string; timing_note: string; exit_note: string; disclaimer: string; }
export interface PillarScore { key: string; label: string; score: number | null; max: number; weight: number; available: boolean; details: Record<string, number | string | null>; }
export interface Indicators { rsi: number | null; macd_signal: string | null; ema_trend: string | null; ema20: number | null; ema50: number | null; ema200: number | null; atr: number | null; bb_position: string | null; volume_ratio: number | null; }
export interface Fundamentals { pe: number | null; pb: number | null; roe_pct: number | null; debt_to_equity: number | null; market_cap: number | null; sector: string | null; industry: string | null; revenue_yoy_pct: number | null; profit_yoy_pct: number | null; eps_yoy_pct: number | null; operating_margin_pct: number | null; latest_ocf: number | null; }
export interface ChartData { dates: string[]; close: number[]; ema20: (number | null)[]; ema50: (number | null)[]; volume: number[]; }
export interface FilterResult { passed: boolean; failures: string[]; }
export interface SuggestionDetail extends SuggestionSummary { trading_day: string; decision: Decision; analyst: AnalystView | null; reasons: Reasons; plan: Plan; score_breakdown: PillarScore[]; indicators: Indicators; fundamentals: Fundamentals; chart: ChartData; filters: FilterResult; }
export interface SuggestionsResponse { run: Run | null; items: SuggestionSummary[]; }

export interface StockRow { symbol: string; close: number; change_1d_pct: number | null; change_1w_pct: number | null; change_1m_pct: number | null; change_3m_pct: number | null; dist_from_52w_high_pct: number | null; volume_ratio_20d: number | null; avg_turnover_lacs: number | null; }
export interface StocksResponse { trading_day: string; total: number; items: StockRow[]; }
export interface StockDetail { symbol: string; trading_day: string; close: number; metrics: StockRow; indicators: Indicators; chart: ChartData; }

export interface Position { id: number; profile_id: number; suggestion_id: number | null; symbol: string; opened_on: string; entry_price: number; qty: number; invested: number; capital: number; cash_left: number; target: number | null; stop_loss: number | null; original_exit_date: string; planned_exit_date: string; status: PositionStatus; last_mark_date: string | null; last_close: number | null; current_value: number | null; pnl: number | null; pnl_pct: number | null; days_held: number; days_to_exit: number | null; closed_on: string | null; exit_price: number | null; close_reason: CloseReason | null; needs_review: boolean; stage: string | null; signal: string | null; }
export interface Mark { mark_date: string; close: number; value: number; pnl: number; pnl_pct: number; }
export interface PositionEvent { id: number; event_date: string; event_type: EventType; old_exit_date: string | null; new_exit_date: string | null; reason: string | null; price: number | null; created_at: string; }
export interface Benchmark { symbol: string; change_pct_since_open: number; }
export interface PositionDetail extends Position { marks: Mark[]; events: PositionEvent[]; suggestion: SuggestionSummary | null; benchmark: Benchmark | null; }
export interface ProfileStats { open: number; due: number; closed: number; wins: number; losses: number; win_rate_pct: number | null; avg_pnl_pct: number | null; avg_win_pct: number | null; avg_loss_pct: number | null; total_pnl: number; realised_pnl: number; unrealised_pnl: number; total_invested: number; best: { symbol: string; pnl_pct: number } | null; worst: { symbol: string; pnl_pct: number } | null; closed_by: Record<CloseReason, number>; extensions: { count: number; helped: number; hurt: number }; pending_reviews: number; }

export interface ReviewTag { key: string; label: string; }
export interface Review { id: number; position_id: number; symbol: string; pnl: number; pnl_pct: number; closed_on: string; close_reason: CloseReason; reasons: string[]; mistakes: string; lesson: string; algo_change: string; reviewed_on: string; created_at: string; }
export interface LossesResponse { pending: Position[]; reviewed: Review[]; }
export interface LossSummary { total_losses: number; reviewed: number; by_tag: { key: string; label: string; count: number }[]; avg_loss_pct: number | null; }

export interface Health { status: string; trading_day: string | null; db: string; }

// Request bodies
export interface CreateProfileBody { name: string; owner?: string; params?: Partial<Params>; }
export interface UpdateProfileBody { name?: string; owner?: string; params?: Partial<Params>; }
export interface StartRunBody { force_refetch?: boolean; }
export interface CreatePositionBody { profile_id: number; suggestion_id?: number; symbol?: string; capital?: number; }
export interface ChangeExitBody { new_exit_date: string; reason: string; }
export interface ClosePositionBody { reason: string; }
export interface NoteBody { note: string; }
export interface ReviewBody { reasons: string[]; mistakes: string; lesson: string; algo_change: string; }

export interface BrainStatus { running: boolean; last_day: string | null; sources: SourceStatus[]; packs_built: number; views_built: number; views_failed: number; }
export interface NightlyBrainBody { day?: string; }
export interface NightlyBrainStarted { job_id: number; }
export interface JobStatus { brain: BrainStatus | null; running: boolean; last_daily_update: string | null; last_trading_day: string | null; next_scheduled: string | null; last_summary: { marked: number; closed_target: number; closed_stop: number; marked_due: number } | null; }
