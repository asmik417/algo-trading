// The "The brain" section's TypeScript snippets, copied verbatim from docs/API_CONTRACT.md. Do not edit by hand.
// Kept in their own module because the section's `Confidence` ('low' | 'medium' | 'high') clashes with the Decision
// section's `Confidence` interface (see "Proposed changes"). Only these imports and the marked block at the end are ours.
import type { Direction, Plan, Verdict } from './api';

export interface SourceStatus {
  source: string;
  day: string;
  status: 'ok' | 'empty' | 'failed';
  records: number;
  error: string | null;
}

export interface QuarterRow {
  period: string;
  filed_on: string | null;
  revenue: number | null;
  ebitda: number | null;
  net_profit: number | null;
  eps: number | null;
  margin_pct: number | null;
}
export interface Ownership {
  as_of: string | null;
  promoter_pct: number | null;
  promoter_change_pct: number | null;
  fii_pct: number | null;
  dii_pct: number | null;
  public_pct: number | null;
  pledge_pct: number | null;
}
export interface DealRow {
  date: string;
  kind: 'bulk' | 'block' | 'insider_buy' | 'insider_sell';
  party: string;
  qty: number;
  price: number | null;
}
export interface EventRow {
  date: string;
  kind: string;
  title: string;
}
export interface Headline {
  date: string;
  title: string;
  source: string;
  url: string;
}
export interface MarketContext {
  day: string;
  nifty_close: number | null;
  nifty_vs_ema50_pct: number | null;
  nifty_1w_pct: number | null;
  vix: number | null;
  advance_decline: number | null;
  fii_net_cr: number | null;
  dii_net_cr: number | null;
  sector_index: string | null;
  sector_1w_pct: number | null;
  sp500_1d_pct: number | null;
  crude_1w_pct: number | null;
  usdinr_1w_pct: number | null;
}
export interface EvidencePack {
  symbol: string;
  day: string;
  price: {
    close: number;
    change_1w_pct: number | null;
    change_1m_pct: number | null;
    change_3m_pct: number | null;
    vs_nifty_1m_pct: number | null;
    vs_sector_1m_pct: number | null;
    dist_52w_high_pct: number | null;
    volume_ratio: number | null;
    delivery_pct_now: number | null;
    delivery_pct_prev: number | null;
    ema_trend: string | null;
    rsi: number | null;
  };
  quarters: QuarterRow[];
  ownership: Ownership | null;
  deals: DealRow[];
  events: EventRow[];
  headlines: Headline[];
  market: MarketContext;
  rules_verdict: Verdict | null;
  plan: Plan | null;
  unavailable: string[];
}

export type Confidence = 'low' | 'medium' | 'high';
export type AnalystAction = 'buy' | 'watch' | 'avoid' | 'add' | 'hold' | 'trim' | 'exit';
export interface AnalystView {
  id: number;
  symbol: string;
  day: string;
  profile_id: number;
  observations: string[];
  anomalies: string[];
  bull_case: string;
  bear_case: string;
  tests: { claim: string; evidence: 'present' | 'absent' | 'unknown'; note: string }[];
  action: AnalystAction;
  direction: Direction;
  horizon_sessions: 20;
  confidence: Confidence;
  trigger: string;
  want_to_know: string;
  agrees_with_rules: boolean | null;
  audited: boolean;
  audit_notes: string[];
  model: string;
  created_at: string;
}

export type Regime = 'risk_on' | 'neutral' | 'risk_off';
export interface MarketBrief {
  day: string;
  regime: Regime;
  context: MarketContext;
  leaders: { index: string; change_1w_pct: number }[];
  laggards: { index: string; change_1w_pct: number }[];
  facts: string[];
  paragraph: string;
  stance: string;
  created_at: string;
}

export type VerdictSource = 'rules' | 'analyst';
export interface LoggedVerdict {
  id: number;
  symbol: string;
  day: string;
  source: VerdictSource;
  profile_id: number;
  action: AnalystAction;
  direction: Direction;
  level: number | null;
  close: number;
  marks: {
    sessions: 20 | 40 | 60;
    date: string;
    close: number;
    change_pct: number;
    right: boolean;
  }[];
}
export interface ScorecardRow {
  key: string;
  verdicts: number;
  marked: number;
  right: number;
  hit_rate_pct: number | null;
  avg_change_pct: number | null;
}
export interface Scorecard {
  profile_id: number;
  source: VerdictSource | 'both';
  horizon: 20 | 40 | 60;
  total: ScorecardRow;
  by_source: ScorecardRow[];
  by_action: ScorecardRow[];
  by_signal: ScorecardRow[];
  by_month: ScorecardRow[];
  worst: LoggedVerdict[];
}

// ---- Frontend extension, pending the contract's TS block (see "Proposed changes") ----------------------------
// The prose says "SuggestionDetail and WatchlistHit gain `analyst: AnalystView | null`" and "GET /jobs/status gains
// `brain`", but the TypeScript blocks do not declare them yet. These names follow the prose exactly.
export type WithAnalyst<T> = T & { analyst: AnalystView | null };
export interface BrainStatus {
  running: boolean;
  last_day: string | null;
  sources: SourceStatus[];
  packs_built: number;
  views_built: number;
  views_failed: number;
}
/** POST /stocks/{symbol}/analyst-view answers 202 { status: 'queued' } or 200 with the view. */
export type AnalystRunResult = { status: 'queued' } | AnalystView;
