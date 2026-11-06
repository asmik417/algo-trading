// Static seed data for mock mode. Shapes follow docs/API_CONTRACT.md; db.ts copies these into mutable state.
// Parameters mirror the live GET /profiles/param-spec (see paramSpec.ts).
import type { Params, Profile, Review, ReviewTag, SuggestionSummary } from '../types/api';
import { NOW_ISO, round } from './dates';
import { PARAM_SPEC } from './paramSpec';

export const HORIZONS = PARAM_SPEC.horizons;
export const CAP_BUCKETS = PARAM_SPEC.cap_buckets;
export { PARAM_SPEC };

/** Scoring pillars come straight from the spec's "Scoring weights" section, so mocks follow the backend's names. */
export const PILLARS: { key: string; label: string; weight: number; weightKey: string }[] = (
  PARAM_SPEC.sections.find((s) => s.section === 'Scoring weights')?.fields ?? []
).map((field) => ({
  key: field.key.replace(/^w_/, ''),
  label: field.label,
  weight: Number(PARAM_SPEC.defaults[field.key]),
  weightKey: field.key,
}));

export const DEFAULT_PARAMS = PARAM_SPEC.defaults as Params;

export function summarizeParams(p: Params): string {
  return `score ≥ ${p.min_score}, top ${p.max_suggestions}, ${p.horizon}, P/E ≤ ${p.max_pe}, ROE ≥ ${p.min_roe_pct}%, RSI ${p.rsi_min}-${p.rsi_max}`;
}

const profileSeed = (
  id: number,
  name: string,
  owner: string,
  active: boolean,
  overrides: Params,
): Profile => {
  const params = { ...DEFAULT_PARAMS, ...overrides };
  return {
    id,
    name,
    owner,
    is_active: active,
    params,
    params_summary: summarizeParams(params),
    created_at: NOW_ISO,
    updated_at: NOW_ISO,
  };
};

export const PROFILE_SEEDS: Profile[] = [
  profileSeed(1, 'Roshan – Early Setups', 'Roshan', true, {}),
  profileSeed(2, 'Manager – Quality Momentum', 'Manager', false, {
    min_score: 70,
    max_suggestions: 10,
    horizon: 'Long (3-6 months)',
    max_pe: 45,
    min_roe_pct: 15,
    rsi_min: 50,
    rsi_max: 70,
    w_earnings_acceleration: 20,
    w_fundamental_quality: 20,
    w_early_price_position: 10,
    w_volume_accumulation: 15,
    w_technical_setup: 20,
    w_valuation: 15,
  }),
  profileSeed(3, 'MD – Large Cap Steady', 'MD', false, {
    allowed_caps: ['Large Cap'],
    min_score: 55,
    max_suggestions: 8,
    horizon: 'Short (2-6 weeks)',
    max_pe: 40,
    min_roe_pct: 12,
    paper_capital: 25000,
  }),
];

// ---------- suggestions (one finished run, 8 stocks) ----------

type SuggestionSeed = Omit<
  SuggestionSummary,
  'id' | 'source' | 'rank' | 'risk_reward' | 'is_tracked' | 'position_id' | 'verdict'
>;
const seed = (s: SuggestionSeed): SuggestionSeed => s;

export const SUGGESTION_SEEDS: SuggestionSeed[] = [
  seed({
    symbol: 'KPITTECH',
    score: 78.4,
    stage: 'Quiet Accumulation',
    signal: '🟢 Early Setup',
    price: 1234.5,
    entry_optimal: 1210,
    stop_loss: 1150,
    target: 1400,
    horizon_days: 50,
    planned_exit_date: '2026-12-24',
    market_cap_bucket: 'Mid Cap',
    sector: 'Technology',
    profit_yoy_pct: 42.1,
    change_1m_pct: 3.2,
    change_3m_pct: 11.0,
    volume_ratio_20d: 1.6,
  }),
  seed({
    symbol: 'CDSL',
    score: 74.9,
    stage: 'Volume Expansion',
    signal: '🟢 Early Setup',
    price: 1480,
    entry_optimal: 1450,
    stop_loss: 1370,
    target: 1680,
    horizon_days: 50,
    planned_exit_date: '2026-12-24',
    market_cap_bucket: 'Mid Cap',
    sector: 'Financial Services',
    profit_yoy_pct: 28.6,
    change_1m_pct: 5.8,
    change_3m_pct: 14.2,
    volume_ratio_20d: 2.1,
  }),
  seed({
    symbol: 'ANGELONE',
    score: 71.2,
    stage: 'Breakout',
    signal: '🔵 Breakout Confirmed',
    price: 2650,
    entry_optimal: 2590,
    stop_loss: 2440,
    target: 3050,
    horizon_days: 45,
    planned_exit_date: '2026-12-19',
    market_cap_bucket: 'Mid Cap',
    sector: 'Financial Services',
    profit_yoy_pct: 35.0,
    change_1m_pct: 9.4,
    change_3m_pct: 21.7,
    volume_ratio_20d: 2.4,
  }),
  seed({
    symbol: 'RADICO',
    score: 68.8,
    stage: 'Quiet Accumulation',
    signal: '🟡 Developing',
    price: 2380,
    entry_optimal: 2330,
    stop_loss: 2210,
    target: 2700,
    horizon_days: 60,
    planned_exit_date: '2027-01-03',
    market_cap_bucket: 'Mid Cap',
    sector: 'Consumer Defensive',
    profit_yoy_pct: 19.3,
    change_1m_pct: 1.1,
    change_3m_pct: 6.5,
    volume_ratio_20d: 1.2,
  }),
  seed({
    symbol: 'KALYANKJIL',
    score: 66.5,
    stage: 'Momentum',
    signal: '🟠 Extended',
    price: 560,
    entry_optimal: 528,
    stop_loss: 495,
    target: 640,
    horizon_days: 35,
    planned_exit_date: '2026-12-09',
    market_cap_bucket: 'Mid Cap',
    sector: 'Consumer Cyclical',
    profit_yoy_pct: 31.8,
    change_1m_pct: 14.9,
    change_3m_pct: 33.4,
    volume_ratio_20d: 1.8,
  }),
  seed({
    symbol: 'SJVN',
    score: 63.1,
    stage: 'Fundamental Change',
    signal: '🟡 Developing',
    price: 108,
    entry_optimal: 105,
    stop_loss: 98,
    target: 126,
    horizon_days: 55,
    planned_exit_date: '2026-12-29',
    market_cap_bucket: 'Mid Cap',
    sector: 'Utilities',
    profit_yoy_pct: 22.4,
    change_1m_pct: 2.0,
    change_3m_pct: 4.8,
    volume_ratio_20d: 1.3,
  }),
  seed({
    symbol: 'NATIONALUM',
    score: 61.7,
    stage: 'Volume Expansion',
    signal: '🟡 Developing',
    price: 214,
    entry_optimal: 208,
    stop_loss: 194,
    target: 246,
    horizon_days: 50,
    planned_exit_date: '2026-12-24',
    market_cap_bucket: 'Mid Cap',
    sector: 'Basic Materials',
    profit_yoy_pct: 55.2,
    change_1m_pct: 4.4,
    change_3m_pct: 12.9,
    volume_ratio_20d: 1.5,
  }),
  seed({
    symbol: 'IRCON',
    score: 60.4,
    stage: 'Fundamental Change',
    signal: '🔴 Weak / Invalidated',
    price: 205,
    entry_optimal: 198,
    stop_loss: 186,
    target: 232,
    horizon_days: 60,
    planned_exit_date: '2027-01-03',
    market_cap_bucket: 'Small Cap',
    sector: 'Industrials',
    profit_yoy_pct: null,
    change_1m_pct: -1.3,
    change_3m_pct: 2.1,
    volume_ratio_20d: 0.9,
  }),
];

export const riskReward = (
  s: Pick<SuggestionSeed, 'entry_optimal' | 'stop_loss' | 'target'>,
): number => round((s.target - s.entry_optimal) / (s.entry_optimal - s.stop_loss), 1);

// ---------- NSE universe for Explore (60 stocks) ----------

export const UNIVERSE: [symbol: string, close: number][] = [
  ['RELIANCE', 2950.4],
  ['TCS', 4120.0],
  ['HDFCBANK', 1685.2],
  ['INFY', 1890.6],
  ['ICICIBANK', 1320.8],
  ['BHARTIARTL', 1710.3],
  ['ITC', 468.9],
  ['SBIN', 842.1],
  ['LT', 3650.7],
  ['HINDUNILVR', 2480.5],
  ['KOTAKBANK', 1980.2],
  ['AXISBANK', 1245.6],
  ['ASIANPAINT', 2390.0],
  ['MARUTI', 12850.0],
  ['SUNPHARMA', 1790.4],
  ['TITAN', 3420.9],
  ['BAJFINANCE', 7150.0],
  ['NTPC', 372.5],
  ['POWERGRID', 318.6],
  ['ULTRACEMCO', 11200.0],
  ['TATAMOTORS', 985.3],
  ['TATASTEEL', 158.9],
  ['WIPRO', 562.4],
  ['HCLTECH', 1745.0],
  ['ONGC', 268.7],
  ['COALINDIA', 482.3],
  ['ADANIPORTS', 1385.0],
  ['JSWSTEEL', 1015.6],
  ['M&M', 3120.4],
  ['TECHM', 1620.8],
  ['KPITTECH', 1234.5],
  ['CDSL', 1480.0],
  ['ANGELONE', 2650.0],
  ['RADICO', 2380.0],
  ['KALYANKJIL', 560.0],
  ['SJVN', 108.0],
  ['NATIONALUM', 214.0],
  ['IRCON', 205.0],
  ['TATAELXSI', 6100.0],
  ['POLYCAB', 6890.0],
  ['PERSISTENT', 5420.0],
  ['DIXON', 15900.0],
  ['SUPREMEIND', 4380.0],
  ['BSE', 2780.0],
  ['MCX', 6350.0],
  ['IRFC', 138.4],
  ['RVNL', 412.7],
  ['HAL', 4510.0],
  ['BEL', 295.4],
  ['TRENT', 5890.0],
  ['ZOMATO', 248.6],
  ['PAYTM', 786.2],
  ['NYKAA', 192.3],
  ['DELHIVERY', 402.8],
  ['IDFCFIRSTB', 71.6],
  ['YESBANK', 21.4],
  ['SUZLON', 58.9],
  ['IREDA', 187.5],
  ['NHPC', 84.2],
  ['HINDCOPPER', 262.0],
];

// ---------- loss-review tags and reviews ----------

export const REVIEW_TAGS: ReviewTag[] = [
  { key: 'bought_extended', label: 'Bought when already extended' },
  { key: 'stop_too_tight', label: 'Stop-loss too tight' },
  { key: 'whole_market_fell', label: 'Whole market fell' },
  { key: 'news_event', label: 'Unexpected news or event' },
  { key: 'poor_entry_timing', label: 'Poor entry timing' },
  { key: 'held_too_long', label: 'Held too long' },
  { key: 'ignored_risk', label: 'Ignored a flagged risk' },
  { key: 'weak_fundamentals', label: 'Weak fundamentals' },
];

export const REVIEW_SEEDS: Review[] = [
  {
    id: 1,
    position_id: 5,
    symbol: 'NATIONALUM',
    pnl: -540,
    pnl_pct: -5.4,
    closed_on: '2026-10-27',
    close_reason: 'stop_hit',
    reasons: ['stop_too_tight', 'whole_market_fell'],
    mistakes:
      'Stop sat only 4% below entry; the Nifty fell 2% that week and the stock tagged the stop on a one-day dip.',
    lesson: 'In a falling market, a 4% stop on a metals stock is inside normal daily noise.',
    algo_change: 'Widen stop to at least 1.5× ATR for Basic Materials.',
    reviewed_on: '2026-10-28',
    created_at: '2026-10-28T08:00:00Z',
  },
  {
    id: 2,
    position_id: 6,
    symbol: 'KALYANKJIL',
    pnl: -310,
    pnl_pct: -3.1,
    closed_on: '2026-10-30',
    close_reason: 'horizon_closed',
    reasons: ['bought_extended', 'poor_entry_timing'],
    mistakes:
      'Entered at the aggressive level after a 30% three-month run; the stock then consolidated until the exit date.',
    lesson: 'Extended stocks need a pullback entry, not a market buy.',
    algo_change: 'Add a max 3-month run-up filter of 30% in my profile.',
    reviewed_on: '2026-10-31',
    created_at: '2026-10-31T08:00:00Z',
  },
];
