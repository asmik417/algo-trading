import type { DailyUpdateStarted, PositionFilter, StockQuery } from '../types/ui';
// In-memory fake backend. Each function mirrors one endpoint of docs/API_CONTRACT.md, including its error cases.
// State lives for the page session; mutations change it so the UI behaves like it is talking to a real server.
import { formatDate, formatINR } from '../lib/format';
import type {
  ChangeExitBody,
  ChartData,
  ClosePositionBody,
  CloseReason,
  CreatePositionBody,
  CreateProfileBody,
  EventType,
  Fundamentals,
  Health,
  Indicators,
  JobStatus,
  LossSummary,
  LossesResponse,
  Mark,
  NoteBody,
  ParamSpec,
  Params,
  PillarScore,
  Plan,
  Position,
  PositionDetail,
  PositionEvent,
  PositionStatus,
  Profile,
  ProfileStats,
  Review,
  ReviewBody,
  ReviewTag,
  Run,
  StockDetail,
  Overall,
  Trend,
  Verdict,
  WatchlistItem,
  PickList,
  CreatePickListBody,
  UpdatePickListBody,
  WatchlistMiss,
  WatchlistResults,
  WatchlistRunBody,
  StockRow,
  StocksResponse,
  SuggestionDetail,
  SuggestionSummary,
  SuggestionsResponse,
  UpdateProfileBody,
} from '../types/api';
import { buildChart } from './chart';
import {
  NOW_ISO,
  TRADING_DAY,
  daysBetween,
  round,
  seeded,
  shiftDays,
  weekdaysBetween,
} from './dates';
import {
  DEFAULT_PARAMS,
  HORIZONS,
  PARAM_SPEC,
  PILLARS,
  PROFILE_SEEDS,
  REVIEW_SEEDS,
  REVIEW_TAGS,
  SUGGESTION_SEEDS,
  UNIVERSE,
  riskReward,
  summarizeParams,
} from './fixtures';
import type { AnalystRunResult, AnalystView, EvidencePack, WithAnalyst } from '../types/brain';
import { signalConfidence } from './backtests';
import * as brain from './brain';
import { buildDecision } from './decision';
import { fail } from './respond';
import { getMockSession } from './session';

export const TODAY = '2026-11-05';

/** Ad-hoc analyses are saved (source "explore") so they can be tracked like any suggestion. */
const ADHOC_ID_START = 10000;

// ---------------------------------------------------------------- suggestions

const HORIZON_DAYS: Record<string, number> = {
  [HORIZONS[0]]: 30,
  [HORIZONS[1]]: 50,
  [HORIZONS[2]]: 120,
};
const SIGNAL_BY_STAGE: Record<string, string> = {
  'Fundamental Change': '🟡 Developing',
  'Quiet Accumulation': '🟢 Early Setup',
  'Volume Expansion': '🟡 Developing',
  Breakout: '🔵 Breakout Confirmed',
  Momentum: '🔵 Breakout Confirmed',
  Extended: '🟠 Extended',
};
const SECTORS = [
  'Technology',
  'Financial Services',
  'Industrials',
  'Healthcare',
  'Consumer Cyclical',
  'Energy',
  'Basic Materials',
];
const INDUSTRIES: Record<string, string> = {
  Technology: 'Software',
  'Financial Services': 'Capital Markets',
  Industrials: 'Engineering',
  Healthcare: 'Drug Manufacturers',
  'Consumer Cyclical': 'Retail',
  Energy: 'Oil & Gas',
  'Basic Materials': 'Metals',
  'Consumer Defensive': 'Beverages',
  Utilities: 'Power',
};

const suggestionId = (profileId: number, index: number): number => profileId * 100 + index + 1;

/** A summary before its verdict is attached. */
type Unverdicted = Omit<SuggestionSummary, 'verdict'>;

function baseSummaries(): Omit<
  SuggestionSummary,
  'id' | 'rank' | 'is_tracked' | 'position_id' | 'verdict'
>[] {
  return SUGGESTION_SEEDS.map((s) => ({
    ...s,
    source: 'run' as const,
    risk_reward: riskReward(s),
  }));
}

function isTracked(profileId: number, symbol: string): Position | undefined {
  return state.positions.find(
    (p) => p.profile_id === profileId && p.symbol === symbol && p.status !== 'closed',
  );
}

/** The suggestions a profile would currently get, after its own score cut-off and list size. */
function suggestionsFor(profile: Profile): SuggestionSummary[] {
  const minScore = Number(profile.params.min_score ?? 0);
  const topN = Number(profile.params.max_suggestions ?? 15);
  const all = baseSummaries();
  const kept = all
    .map((s, index) => ({ s, index }))
    .filter(({ s }) => s.score >= minScore)
    .slice(0, topN);
  return kept.map(({ s, index }, i) => {
    const pos = isTracked(profile.id, s.symbol);
    return withVerdict(
      {
        ...s,
        id: suggestionId(profile.id, index),
        rank: i + 1,
        is_tracked: !!pos,
        position_id: pos?.id ?? null,
      },
      profile,
      true,
    );
  });
}

function universeClose(symbol: string): number | undefined {
  return UNIVERSE.find(([s]) => s === symbol)?.[1];
}

/** A summary for a stock that is not in the algo's list (Explore → analyse). */
function syntheticSummary(
  id: number,
  symbol: string,
  close: number,
  profile: Profile,
): SuggestionSummary {
  const rand = seeded(`analyze:${symbol}`);
  const stages = Object.keys(SIGNAL_BY_STAGE);
  const stage = stages[Math.floor(rand() * stages.length)];
  const score = round(38 + rand() * 42, 1);
  const days = HORIZON_DAYS[String(profile.params.horizon)] ?? 50;
  const sector = SECTORS[Math.floor(rand() * SECTORS.length)];
  const entry = round(close * 0.98, 1);
  const stop = round(close * 0.92, 1);
  const target = round(close * 1.14, 1);
  const base: Unverdicted = {
    id,
    source: 'explore',
    symbol,
    rank: null,
    score,
    stage,
    signal: score < 50 ? '🔴 Weak / Invalidated' : SIGNAL_BY_STAGE[stage],
    price: close,
    entry_optimal: entry,
    stop_loss: stop,
    target,
    risk_reward: riskReward({ entry_optimal: entry, stop_loss: stop, target }),
    horizon_days: days,
    planned_exit_date: shiftDays(TRADING_DAY, days),
    market_cap_bucket: close > 2000 ? 'Large Cap' : close > 300 ? 'Mid Cap' : 'Small Cap',
    sector,
    profit_yoy_pct: rand() < 0.15 ? null : round(-10 + rand() * 60, 1),
    change_1m_pct: round(-8 + rand() * 20, 1),
    change_3m_pct: round(-12 + rand() * 40, 1),
    volume_ratio_20d: round(0.6 + rand() * 1.9, 1),
    is_tracked: !!isTracked(profile.id, symbol),
    position_id: isTracked(profile.id, symbol)?.id ?? null,
  };
  return withVerdict(base, profile, false);
}

/** ema_trend from the last ~63 sessions of the chart, so mock trends vary realistically. */
function trendOf(chart: ChartData): string {
  const n = chart.close.length;
  if (n < 2) return 'SIDEWAYS';
  const change = (chart.close[n - 1] / chart.close[Math.max(0, n - 64)] - 1) * 100;
  return change > 12
    ? 'STRONG_UPTREND'
    : change > 4
      ? 'UPTREND'
      : change < -4
        ? 'DOWNTREND'
        : 'SIDEWAYS';
}
const isDown = (t: string | null) =>
  t === 'STRONG_DOWNTREND' || t === 'BELOW_200EMA' || t === 'DOWNTREND';
const isUp = (t: string | null) =>
  t === 'STRONG_UPTREND' || t === 'ABOVE_200EMA' || t === 'UPTREND';

function buildIndicators(
  symbol: string,
  price: number,
  chart: ChartData,
  volumeRatio: number | null,
): Indicators {
  const rand = seeded(`ind:${symbol}`);
  const last = (a: (number | null)[]) => a[a.length - 1] ?? null;
  const rsi = round(38 + rand() * 40, 1);
  const bb = Math.round(20 + rand() * 70);
  return {
    rsi,
    macd_signal: rand() > 0.3 ? 'BULLISH' : 'NEUTRAL',
    ema_trend: trendOf(chart),
    ema20: last(chart.ema20),
    ema50: last(chart.ema50),
    ema200: round(
      price * (isDown(trendOf(chart)) ? 1.07 : trendOf(chart) === 'SIDEWAYS' ? 1.01 : 0.86),
      2,
    ),
    atr: round(price * 0.023, 1),
    bb_position: `${bb > 66 ? 'UPPER' : bb < 33 ? 'LOWER' : 'MID'} (${bb}% from lower band)`,
    volume_ratio: volumeRatio,
  };
}

function buildFundamentals(s: Unverdicted): Fundamentals {
  const rand = seeded(`fund:${s.symbol}`);
  const profit = s.profit_yoy_pct;
  return {
    pe: round(16 + rand() * 42, 1),
    pb: round(1.5 + rand() * 8, 1),
    roe_pct: round(8 + rand() * 24, 1),
    debt_to_equity: round(rand() * 90, 1),
    market_cap: Math.round(s.price * (2e7 + rand() * 4e8)),
    sector: s.sector,
    industry: s.sector ? (INDUSTRIES[s.sector] ?? null) : null,
    revenue_yoy_pct: profit === null ? null : round(profit * 0.45, 1),
    profit_yoy_pct: profit,
    eps_yoy_pct: profit === null ? null : round(profit * 0.95, 1),
    operating_margin_pct: round(8 + rand() * 20, 1),
    latest_ocf: Math.round((1 + rand() * 9) * 1e9),
  };
}

function buildBreakdown(s: SuggestionSummary, profile: Profile): PillarScore[] {
  const rand = seeded(`pillars:${s.symbol}`);
  return PILLARS.map((p) => {
    const weight = Number(profile.params[p.weightKey] ?? p.weight);
    // No profit data → the earnings pillar is skipped, never filled with 0 (CLAUDE.md rule 6).
    const available = !(p.key === 'earnings_acceleration' && s.profit_yoy_pct === null);
    const details: PillarScore['details'] =
      p.key === 'earnings_acceleration'
        ? {
            revenue_yoy_pct: s.profit_yoy_pct === null ? null : round(s.profit_yoy_pct * 0.45, 1),
            profit_yoy_pct: s.profit_yoy_pct,
          }
        : p.key === 'volume_expansion'
          ? { volume_ratio_20d: s.volume_ratio_20d }
          : {};
    return {
      key: p.key,
      label: p.label,
      weight,
      max: weight,
      available,
      score: available ? round(weight * (0.45 + rand() * 0.5), 1) : null,
      details,
    };
  });
}

function buildPlan(s: SuggestionSummary): Plan {
  return {
    entry_aggressive: s.price,
    entry_optimal: s.entry_optimal,
    entry_conservative: round(s.entry_optimal * 0.975, 1),
    stop_loss: s.stop_loss,
    target: s.target,
    risk_reward: s.risk_reward,
    horizon_days: s.horizon_days,
    planned_exit_date: s.planned_exit_date,
    timing_note: `Accumulate on pullbacks toward ${formatINR(s.entry_optimal)} (20-day EMA) over the next 5-10 sessions; avoid chasing above ${formatINR(round(s.price * 1.02, 1))}.`,
    exit_note: `Book profit at ${formatINR(s.target)} or exit on close below ${formatINR(s.stop_loss)}. Re-assess on ${formatDate(s.planned_exit_date)} if neither is hit.`,
    disclaimer:
      'This plan is rules-based and may vary with news and live market updates. Paper trading only.',
  };
}

function buildReasons(s: SuggestionSummary, rsi: number | null): SuggestionDetail['reasons'] {
  const profit = s.profit_yoy_pct;
  const move = s.change_1m_pct;
  // Only narrate profit growth as a strength when it is clearly positive.
  const growing = profit !== null && profit > 5;
  const positives: string[] = [];
  const risks: string[] = [];
  if (profit !== null && growing)
    positives.push(
      `Profit growth (${round(profit, 0)}%) is outpacing revenue growth (${round(profit * 0.45, 0)}%).`,
    );
  if (s.volume_ratio_20d !== null && s.volume_ratio_20d >= 1.4)
    positives.push(`Volume is ${s.volume_ratio_20d}× its 20-day average, a sign of accumulation.`);
  if (s.risk_reward >= 1.8)
    positives.push(`Risk-reward of ${s.risk_reward}:1 at the optimal entry.`);
  if (rsi !== null && rsi >= 65) risks.push(`RSI at ${round(rsi, 0)} — approaching overbought.`);
  if (s.change_3m_pct !== null && s.change_3m_pct > 30)
    risks.push(`Already up ${s.change_3m_pct}% in three months; entering now chases the move.`);
  if (profit === null)
    risks.push(
      'Profit growth is unavailable for this stock, so that part of the score was skipped.',
    );
  if (risks.length === 0)
    risks.push('A broad market fall would hit this stock even if its setup holds.');
  return {
    why_flagged:
      profit === null
        ? `${s.symbol} was flagged mainly on price and volume behaviour. Earnings data is unavailable, so that component was not scored.`
        : !growing
          ? `${s.symbol} was flagged on price and volume behaviour; profit growth is weak (${round(profit, 0)}% year on year), so earnings count little in its score.`
          : `${s.symbol} was flagged because its latest-quarter profit grew ${round(profit, 0)}% year on year while the stock moved only ${move === null ? '—' : `${round(move, 0)}%`} in the past month, and volume is running ${s.volume_ratio_20d ?? '—'}× its 20-day average.`,
    what_changed:
      profit === null
        ? 'Earnings data was not available to compare against price.'
        : !growing
          ? `Latest quarter profit changed ${round(profit, 0)}% year on year; no earnings-driven change detected.`
          : `Latest quarter profit grew ${round(profit, 0)}% while the stock moved only ${move === null ? '—' : `${round(move, 0)}%`}.`,
    positives,
    risks,
  };
}

/** Every hard rule that could be evaluated; a rule whose metric is unavailable is skipped, not failed. */
function evaluateRules(
  s: Unverdicted,
  f: Fundamentals,
  ind: Indicators,
  p: Params,
): { total: number; failures: string[] } {
  const failures: string[] = [];
  let total = 0;
  const rule = (available: boolean, failed: () => boolean, text: () => string) => {
    if (!available) return;
    total++;
    if (failed()) failures.push(text());
  };
  rule(
    true,
    () => s.score < Number(p.min_score),
    () => `Score ${s.score} below min ${p.min_score}`,
  );
  rule(
    f.pe !== null,
    () => (f.pe ?? 0) > Number(p.max_pe),
    () => `P/E ${round(f.pe ?? 0, 0)} above max ${p.max_pe}`,
  );
  rule(
    f.roe_pct !== null,
    () => (f.roe_pct ?? 0) < Number(p.min_roe_pct),
    () => `ROE ${round(f.roe_pct ?? 0, 0)}% below min ${p.min_roe_pct}%`,
  );
  rule(
    f.debt_to_equity !== null,
    () => (f.debt_to_equity ?? 0) > Number(p.max_debt_to_equity),
    () => `Debt/equity ${round(f.debt_to_equity ?? 0, 0)} above max ${p.max_debt_to_equity}`,
  );
  rule(
    ind.rsi !== null,
    () => (ind.rsi ?? 0) > Number(p.rsi_max),
    () => `RSI ${round(ind.rsi ?? 0, 0)} above max ${p.rsi_max}`,
  );
  rule(
    ind.rsi !== null,
    () => (ind.rsi ?? 0) < Number(p.rsi_min),
    () => `RSI ${round(ind.rsi ?? 0, 0)} below min ${p.rsi_min}`,
  );
  rule(
    s.change_3m_pct !== null,
    () => (s.change_3m_pct ?? 0) > Number(p.max_3m_runup_pct),
    () => `3-month run-up ${s.change_3m_pct}% above max ${p.max_3m_runup_pct}%`,
  );
  rule(
    s.profit_yoy_pct !== null,
    () => (s.profit_yoy_pct ?? 0) < Number(p.min_profit_growth_pct),
    () => `Profit growth ${round(s.profit_yoy_pct ?? 0, 0)}% below min ${p.min_profit_growth_pct}%`,
  );
  rule(
    s.volume_ratio_20d !== null,
    () => (s.volume_ratio_20d ?? 0) < Number(p.min_volume_ratio),
    () => `Volume ${s.volume_ratio_20d}x 20-day average, below min ${p.min_volume_ratio}x`,
  );
  return { total, failures };
}

function checkFilters(
  s: Unverdicted,
  f: Fundamentals,
  ind: Indicators,
  p: Params,
): SuggestionDetail['filters'] {
  const { failures } = evaluateRules(s, f, ind, p);
  // Informational notes: the backend may add these to `failures` while `passed` stays true.
  const notes: string[] = [];
  if (s.profit_yoy_pct === null) notes.push('Profit growth unavailable, filter skipped');
  return { passed: failures.length === 0, failures: failures.length ? failures : notes };
}

/** The contract's three-part verdict (section "Verdict"), computed deterministically from the stock's own numbers. */
function verdictFor(s: Unverdicted, profile: Profile, passedAllRules: boolean): Verdict {
  const chart = buildChart(s.symbol, s.price, s.change_3m_pct ?? 0);
  const ind = buildIndicators(s.symbol, s.price, chart, s.volume_ratio_20d);
  const rules = evaluateRules(s, buildFundamentals(s), ind, profile.params);
  const failures = passedAllRules ? [] : rules.failures;
  const trend: Trend = isUp(ind.ema_trend)
    ? 'uptrend'
    : isDown(ind.ema_trend)
      ? 'downtrend'
      : 'sideways';
  const weak = s.signal.includes('Weak');
  const phrase = weak
    ? 'weak'
    : s.signal.includes('Breakout Confirmed')
      ? 'breakout confirmed'
      : s.stage.toLowerCase();
  const label = `${trend.charAt(0).toUpperCase()}${trend.slice(1)}, ${phrase}`;
  const points = [
    ind.ema200 !== null && s.price >= ind.ema200 ? 'Above 200-day EMA' : 'Below 200-day EMA',
    ...(ind.rsi !== null ? [`RSI ${round(ind.rsi, 0)}`] : []),
    ...(s.volume_ratio_20d !== null ? [`Volume ${s.volume_ratio_20d}x`] : []),
  ];
  const goodSignal = ['Early Setup', 'Breakout Confirmed', 'Developing'].some((x) =>
    s.signal.includes(x),
  );
  const overall: Overall =
    weak ||
    trend === 'downtrend' ||
    (s.profit_yoy_pct !== null && s.profit_yoy_pct < 0) ||
    failures.length > 2
      ? 'avoid'
      : failures.length === 0 && trend === 'uptrend' && goodSignal
        ? 'buy'
        : 'watch';
  return {
    overall,
    rules: { passed: rules.total - failures.length, total: rules.total, failures },
    chart: { trend, label, points },
    reason: `${failures[0] ?? 'Passes all rules'}; ${label.charAt(0).toLowerCase()}${label.slice(1)}.`,
  };
}

function withVerdict<T extends Unverdicted>(
  s: T,
  profile: Profile,
  passedAllRules: boolean,
): T & { verdict: Verdict } {
  return { ...s, verdict: verdictFor(s, profile, passedAllRules) };
}

function buildDetail(
  s: SuggestionSummary,
  profile: Profile,
  checkAgainstProfile: boolean,
): SuggestionDetail {
  const chart = buildChart(s.symbol, s.price, s.change_3m_pct ?? 0);
  const indicators = buildIndicators(s.symbol, s.price, chart, s.volume_ratio_20d);
  const fundamentals = buildFundamentals(s);
  const plan = buildPlan(s);
  return {
    ...s,
    trading_day: TRADING_DAY,
    decision: buildDecision(
      s,
      plan,
      indicators,
      fundamentals,
      chart,
      signalConfidence(profile.id, s.signal),
    ),
    reasons: buildReasons(s, indicators.rsi),
    plan,
    score_breakdown: buildBreakdown(s, profile),
    indicators,
    fundamentals,
    chart,
    filters: checkAgainstProfile
      ? checkFilters(s, fundamentals, indicators, profile.params)
      : { passed: true, failures: [] },
  };
}

// ---------------------------------------------------------------- positions

interface PositionSeed {
  id: number;
  symbol: string;
  suggestionId: number | null;
  openedOn: string;
  entry: number;
  last: number;
  target: number;
  stop: number;
  originalExit: number | string;
  plannedExit: string;
  status: PositionStatus;
  exitPrice?: number;
  closedOn?: string;
  closeReason?: CloseReason;
  closeNote?: string;
  needsReview?: boolean;
  extend?: { date: string; reason: string };
  benchmark: number;
  stage: string;
  signal: string;
}

const POSITION_SEEDS: PositionSeed[] = [
  {
    id: 1,
    symbol: 'KPITTECH',
    suggestionId: 101,
    openedOn: '2026-10-21',
    entry: 1180,
    last: 1234.5,
    target: 1400,
    stop: 1150,
    originalExit: '2026-12-10',
    plannedExit: '2026-12-10',
    status: 'open',
    benchmark: 1.2,
    stage: 'Quiet Accumulation',
    signal: '🟢 Early Setup',
  },
  {
    id: 2,
    symbol: 'CDSL',
    suggestionId: 102,
    openedOn: '2026-10-28',
    entry: 1415,
    last: 1480,
    target: 1680,
    stop: 1370,
    originalExit: '2026-12-17',
    plannedExit: '2026-12-17',
    status: 'open',
    benchmark: 0.6,
    stage: 'Volume Expansion',
    signal: '🟢 Early Setup',
  },
  {
    id: 3,
    symbol: 'SJVN',
    suggestionId: null,
    openedOn: '2026-09-18',
    entry: 101,
    last: 108,
    target: 126,
    stop: 94,
    originalExit: '2026-11-04',
    plannedExit: '2026-11-04',
    status: 'due',
    benchmark: 2.1,
    stage: 'Fundamental Change',
    signal: '🟡 Developing',
  },
  {
    id: 4,
    symbol: 'IRCON',
    suggestionId: null,
    openedOn: '2026-09-15',
    entry: 170,
    last: 191,
    target: 190,
    stop: 158,
    originalExit: '2026-10-20',
    plannedExit: '2026-11-03',
    status: 'closed',
    exitPrice: 191,
    closedOn: '2026-10-22',
    closeReason: 'target_hit',
    extend: {
      date: '2026-10-19',
      reason: 'Strong volume, order-book news due; giving it two more weeks.',
    },
    benchmark: 1.8,
    stage: 'Breakout',
    signal: '🔵 Breakout Confirmed',
  },
  {
    id: 5,
    symbol: 'NATIONALUM',
    suggestionId: null,
    openedOn: '2026-10-13',
    entry: 225,
    last: 213,
    target: 262,
    stop: 213,
    originalExit: '2026-10-23',
    plannedExit: '2026-11-10',
    status: 'closed',
    exitPrice: 213,
    closedOn: '2026-10-27',
    closeReason: 'stop_hit',
    extend: {
      date: '2026-10-22',
      reason: 'Still above the 50-day average, extending to let the setup play out.',
    },
    benchmark: -1.9,
    stage: 'Volume Expansion',
    signal: '🟡 Developing',
  },
  {
    id: 6,
    symbol: 'KALYANKJIL',
    suggestionId: null,
    openedOn: '2026-09-21',
    entry: 548,
    last: 531,
    target: 640,
    stop: 495,
    originalExit: '2026-10-30',
    plannedExit: '2026-10-30',
    status: 'closed',
    exitPrice: 531,
    closedOn: '2026-10-30',
    closeReason: 'horizon_closed',
    benchmark: 0.9,
    stage: 'Momentum',
    signal: '🟠 Extended',
  },
  {
    id: 7,
    symbol: 'ANGELONE',
    suggestionId: null,
    openedOn: '2026-10-05',
    entry: 2790,
    last: 2680,
    target: 3200,
    stop: 2580,
    originalExit: '2026-11-19',
    plannedExit: '2026-11-19',
    status: 'closed',
    exitPrice: 2680,
    closedOn: '2026-10-30',
    closeReason: 'manual',
    closeNote: 'Broke below the 50-day average on heavy volume; exiting before the stop.',
    needsReview: true,
    benchmark: 0.4,
    stage: 'Breakout',
    signal: '🔵 Breakout Confirmed',
  },
];

function buildMarks(seed: PositionSeed, qty: number): Mark[] {
  const rand = seeded(`marks:${seed.symbol}`);
  const days = weekdaysBetween(shiftDays(seed.openedOn, 1), seed.closedOn ?? TRADING_DAY);
  const finalClose = seed.exitPrice ?? seed.last;
  const invested = qty * seed.entry;
  return days.map((mark_date, i) => {
    const t = (i + 1) / days.length;
    const wobble = i === days.length - 1 ? 0 : (rand() - 0.5) * seed.entry * 0.02 * (1 - t * 0.6);
    const close = round(seed.entry + (finalClose - seed.entry) * t + wobble, 2);
    const value = round(qty * close, 2);
    return {
      mark_date,
      close,
      value,
      pnl: round(value - invested, 2),
      pnl_pct: round(((value - invested) / invested) * 100, 2),
    };
  });
}

/** Recomputes every derived field from marks, status and dates. Call after any change. */
function derive(p: PositionDetail): PositionDetail {
  const lastMark = p.marks[p.marks.length - 1] ?? null;
  const close = p.status === 'closed' ? p.exit_price : (lastMark?.close ?? p.entry_price);
  p.last_mark_date = lastMark?.mark_date ?? p.opened_on;
  p.last_close = close;
  p.current_value = close === null ? null : round(p.qty * close, 2);
  p.pnl = p.current_value === null ? null : round(p.current_value - p.invested, 2);
  p.pnl_pct = p.pnl === null ? null : round((p.pnl / p.invested) * 100, 2);
  p.days_held = daysBetween(p.opened_on, p.closed_on ?? p.last_mark_date);
  p.days_to_exit =
    p.status === 'closed' ? null : daysBetween(p.last_mark_date, p.planned_exit_date);
  return p;
}

function addEvent(p: PositionDetail, e: Omit<PositionEvent, 'id' | 'created_at'>): void {
  const id = p.events.reduce((m, ev) => Math.max(m, ev.id), 0) + 1;
  p.events.push({ ...e, id, created_at: `${e.event_date}T09:00:00Z` });
}

const CLOSE_TEXT: Record<CloseReason, string> = {
  target_hit: 'Target price reached.',
  stop_hit: 'Stop-loss triggered.',
  horizon_closed: 'Planned exit date reached; closed at the day’s close.',
  manual: 'Closed manually.',
};

function buildPosition(s: PositionSeed): PositionDetail {
  const capital = 10000;
  const qty = Math.floor(capital / s.entry);
  const invested = round(qty * s.entry, 2);
  // Built straight from the seeds: this runs while `state` is still being created, so it must not read `state`.
  const seedIndex = s.suggestionId === null ? -1 : (s.suggestionId % 100) - 1;
  const base = baseSummaries()[seedIndex];
  const summary: SuggestionSummary | null =
    base && s.suggestionId !== null
      ? withVerdict(
          { ...base, id: s.suggestionId, rank: seedIndex + 1, is_tracked: true, position_id: s.id },
          PROFILE_SEEDS[0],
          true,
        )
      : null;
  const d: PositionDetail = {
    id: s.id,
    profile_id: 1,
    suggestion_id: s.suggestionId,
    symbol: s.symbol,
    opened_on: s.openedOn,
    entry_price: s.entry,
    qty,
    invested,
    capital,
    cash_left: round(capital - invested, 2),
    target: s.target,
    stop_loss: s.stop,
    original_exit_date: String(s.originalExit),
    planned_exit_date: s.plannedExit,
    status: s.status,
    last_mark_date: null,
    last_close: null,
    current_value: null,
    pnl: null,
    pnl_pct: null,
    days_held: 0,
    days_to_exit: null,
    closed_on: s.closedOn ?? null,
    exit_price: s.exitPrice ?? null,
    close_reason: s.closeReason ?? null,
    needs_review: s.needsReview ?? false,
    stage: s.stage,
    signal: s.signal,
    marks: buildMarks(s, qty),
    events: [],
    suggestion: summary,
    benchmark: { symbol: 'NIFTY 50', change_pct_since_open: s.benchmark },
  };
  addEvent(d, {
    event_date: s.openedOn,
    event_type: 'open',
    old_exit_date: null,
    new_exit_date: String(s.originalExit),
    reason: null,
    price: s.entry,
  });
  if (s.extend)
    addEvent(d, {
      event_date: s.extend.date,
      event_type: 'extend',
      old_exit_date: String(s.originalExit),
      new_exit_date: s.plannedExit,
      reason: s.extend.reason,
      price: null,
    });
  if (s.status === 'due')
    addEvent(d, {
      event_date: TRADING_DAY,
      event_type: 'due',
      old_exit_date: null,
      new_exit_date: s.plannedExit,
      reason: 'Planned exit date reached.',
      price: s.last,
    });
  if (s.closedOn && s.closeReason)
    addEvent(d, {
      event_date: s.closedOn,
      event_type: 'close',
      old_exit_date: null,
      new_exit_date: null,
      reason: s.closeNote ?? CLOSE_TEXT[s.closeReason],
      price: s.exitPrice ?? null,
    });
  return derive(d);
}

const DETAIL_ONLY_KEYS = new Set(['marks', 'events', 'suggestion', 'benchmark']);
function toPosition(d: PositionDetail): Position {
  return Object.fromEntries(
    Object.entries(d).filter(([k]) => !DETAIL_ONLY_KEYS.has(k)),
  ) as unknown as Position;
}

// ---------------------------------------------------------------- state

interface RunClock {
  startedMs: number;
}
interface MockState {
  profiles: Profile[];
  nextProfileId: number;
  runs: Run[];
  nextRunId: number;
  positions: PositionDetail[];
  nextPositionId: number;
  reviews: Review[];
  nextReviewId: number;
  adhoc: { profileId: number; detail: SuggestionDetail }[];
  nextAdhocId: number;
  /** Results of finished watchlist runs, frozen when the run finishes (like rows in the real database). */
  watchlistResults: Map<number, WatchlistItem[]>;
  pickLists: PickList[];
  nextPickListId: number;
  job: { runningUntilMs: number; status: JobStatus };
}

function initialState(): MockState {
  const state = {
    profiles: structuredClone(PROFILE_SEEDS),
    nextProfileId: 4,
    runs: [
      {
        id: 7,
        profile_id: 1,
        status: 'done',
        kind: 'full',
        symbols: null,
        list_id: null,
        list_name: null,
        trading_day: TRADING_DAY,
        progress: { phase: 'done', done: 231, total: 231, current_symbol: null },
        universe_size: 2612,
        scored_size: 231,
        passed_size: SUGGESTION_SEEDS.length,
        error: null,
        started_at: '2026-11-05T05:00:00Z',
        finished_at: '2026-11-05T05:01:10Z',
        created_at: '2026-11-05T05:00:00Z',
      } satisfies Run,
      {
        id: 6,
        profile_id: 1,
        status: 'done',
        kind: 'watchlist',
        symbols: ['RELIANCE', 'KPITTECH', 'TITAN', 'NHPC', 'NOTREAL'],
        list_id: 3,
        list_name: 'Watch candidates',
        trading_day: TRADING_DAY,
        progress: { phase: 'done', done: 5, total: 5, current_symbol: null },
        universe_size: 5,
        scored_size: 4,
        passed_size: null,
        error: null,
        started_at: '2026-11-04T12:00:00Z',
        finished_at: '2026-11-04T12:00:04Z',
        created_at: '2026-11-04T12:00:00Z',
      } satisfies Run,
    ],
    nextRunId: 8,
    positions: [] as PositionDetail[],
    nextPositionId: 8,
    reviews: [] as Review[],
    nextReviewId: 3,
    adhoc: [] as { profileId: number; detail: SuggestionDetail }[],
    nextAdhocId: ADHOC_ID_START + 1,
    watchlistResults: new Map<number, WatchlistItem[]>(),
    pickLists: [
      {
        id: 1,
        name: 'Manager holdings',
        symbols: ['RELIANCE', 'TCS', 'INFY', 'ITC', 'HDFCBANK'],
        created_at: '2026-11-03T10:00:00Z',
        updated_at: '2026-11-03T10:00:00Z',
      },
      {
        id: 2,
        name: 'Momentum ideas',
        symbols: ['KPITTECH', 'ANGELONE', 'CDSL', 'TRENT', 'DIXON'],
        created_at: '2026-11-04T09:00:00Z',
        updated_at: '2026-11-04T09:00:00Z',
      },
      {
        id: 3,
        name: 'Watch candidates',
        symbols: ['RELIANCE', 'KPITTECH', 'TITAN', 'NHPC', 'NOTREAL'],
        created_at: '2026-11-04T11:55:00Z',
        updated_at: '2026-11-04T11:55:00Z',
      },
    ] as PickList[],
    nextPickListId: 4,
    job: {
      runningUntilMs: 0,
      status: {
        running: false,
        last_daily_update: '2026-11-04T13:05:00Z',
        last_trading_day: TRADING_DAY,
        next_scheduled: '2026-11-05T13:00:00Z',
        last_summary: { marked: 7, closed_target: 1, closed_stop: 0, marked_due: 1 },
      } satisfies JobStatus,
    },
  };
  state.positions = POSITION_SEEDS.map(buildPosition).sort((a, b) => b.id - a.id);
  // Review numbers always agree with their position, so seeds cannot drift out of sync.
  state.reviews = structuredClone(REVIEW_SEEDS).map((r) => {
    const p = state.positions.find((x) => x.id === r.position_id);
    return p && p.pnl !== null && p.pnl_pct !== null && p.closed_on && p.close_reason
      ? {
          ...r,
          pnl: p.pnl,
          pnl_pct: p.pnl_pct,
          closed_on: p.closed_on,
          close_reason: p.close_reason,
        }
      : r;
  });
  return state;
}

let state: MockState = initialState();
const runClocks = new Map<number, RunClock>();

/** Test/debug helper: back to the seeded world. */
export function resetMockDb(): void {
  state = initialState();
  runClocks.clear();
}

// ---------------------------------------------------------------- profiles

function findProfile(id: number): Profile {
  return state.profiles.find((p) => p.id === id) ?? fail(404, `Profile ${id} not found`);
}

/** Layers a partial params object over a full one. Unknown keys are rejected like the real API does. */
function mergeParams(base: Params, partial: Partial<Params> | undefined): Params {
  const merged: Params = { ...base };
  const unknown: string[] = [];
  for (const [key, value] of Object.entries(partial ?? {})) {
    if (!(key in DEFAULT_PARAMS)) unknown.push(key);
    else if (value !== undefined) merged[key] = value;
  }
  if (unknown.length) fail(400, `Unknown parameter(s): ${unknown.join(', ')}`);
  return merged;
}

function validateParams(p: Params): void {
  const problems: string[] = [];
  const weights = Object.entries(p)
    .filter(([k]) => k.startsWith('w_'))
    .reduce((sum, [, v]) => sum + Number(v), 0);
  if (weights !== 100) problems.push(`Scoring weights add up to ${weights}; they must total 100`);
  if (Number(p.rsi_min) >= Number(p.rsi_max))
    problems.push('Minimum RSI must be below maximum RSI');
  if (Number(p.min_score) < 0 || Number(p.min_score) > 100)
    problems.push('Minimum score must be between 0 and 100');
  if (Number(p.max_suggestions) < 1) problems.push('Maximum suggestions must be at least 1');
  if (Array.isArray(p.allowed_caps) && p.allowed_caps.length === 0)
    problems.push('Pick at least one market cap bucket');
  if (problems.length) fail(400, problems.join('; '));
}

export const getHealth = (): Health => ({ status: 'ok', trading_day: TRADING_DAY, db: 'ok' });
export const getParamSpec = (): ParamSpec => PARAM_SPEC;
export const listProfiles = (): Profile[] => state.profiles;
export const getProfile = (id: number): Profile => findProfile(id);
export const getActiveProfile = (): Profile =>
  state.profiles.find((p) => p.is_active) ?? fail(404, 'No active profile');

export function createProfile(body: CreateProfileBody): Profile {
  if (!body.name?.trim()) fail(400, 'Name is required');
  if (state.profiles.some((p) => p.name.toLowerCase() === body.name.trim().toLowerCase()))
    fail(409, `A profile named "${body.name.trim()}" already exists`);
  const params = mergeParams(DEFAULT_PARAMS, body.params);
  validateParams(params);
  const profile: Profile = {
    id: state.nextProfileId++,
    name: body.name.trim(),
    owner: body.owner?.trim() || (getMockSession() ?? 'roshan'),
    is_active: state.profiles.length === 0,
    params,
    params_summary: summarizeParams(params),
    created_at: NOW_ISO,
    updated_at: NOW_ISO,
  };
  state.profiles.push(profile);
  return profile;
}

export function updateProfile(id: number, body: UpdateProfileBody): Profile {
  const profile = findProfile(id);
  if (body.name !== undefined && !body.name.trim()) fail(400, 'Name cannot be empty');
  if (body.owner !== undefined && !body.owner.trim()) fail(400, 'Owner cannot be empty');
  if (
    body.name !== undefined &&
    state.profiles.some(
      (p) => p.id !== id && p.name.toLowerCase() === body.name?.trim().toLowerCase(),
    )
  )
    fail(409, `A profile named "${body.name.trim()}" already exists`);
  const params = mergeParams(profile.params, body.params);
  validateParams(params);
  Object.assign(profile, {
    name: body.name?.trim() ?? profile.name,
    owner: body.owner?.trim() ?? profile.owner,
    params,
    params_summary: summarizeParams(params),
    updated_at: new Date().toISOString(),
  });
  return profile;
}

export function deleteProfile(id: number): void {
  findProfile(id);
  state.profiles = state.profiles.filter((p) => p.id !== id);
}

export function activateProfile(id: number): Profile {
  const profile = findProfile(id);
  state.profiles.forEach((p) => (p.is_active = p.id === id));
  return profile;
}

// ---------------------------------------------------------------- runs

function refreshRun(run: Run): Run {
  if (run.status === 'done' || run.status === 'failed') return run;
  if (run.kind === 'watchlist') return refreshWatchlistRun(run);
  const clock = runClocks.get(run.id);
  const elapsed = clock ? Date.now() - clock.startedMs : Infinity;
  if (elapsed < 800) return run;
  const f = Math.min(1, (elapsed - 800) / 6200);
  if (f >= 1) {
    const profile = state.profiles.find((p) => p.id === run.profile_id);
    Object.assign(run, {
      status: 'done',
      trading_day: TRADING_DAY,
      progress: { phase: 'done', done: 250, total: 250, current_symbol: null },
      universe_size: 2612,
      scored_size: 231,
      passed_size: profile ? suggestionsFor(profile).length : 0,
      started_at: run.started_at ?? NOW_ISO,
      finished_at: new Date().toISOString(),
    });
    return run;
  }
  const symbols = UNIVERSE.map(([s]) => s);
  const phase =
    f < 0.1
      ? 'panel'
      : f < 0.25
        ? 'prefilter'
        : f < 0.75
          ? 'scoring'
          : f < 0.85
            ? 'filtering'
            : f < 0.95
              ? 'planning'
              : 'saving';
  const done =
    phase === 'scoring'
      ? Math.round(((f - 0.25) / 0.5) * 250)
      : phase === 'panel' || phase === 'prefilter'
        ? 0
        : 250;
  run.status = 'running';
  run.started_at = run.started_at ?? new Date(clock?.startedMs ?? Date.now()).toISOString();
  run.progress = {
    phase,
    done,
    total: phase === 'panel' ? 0 : 250,
    current_symbol: phase === 'scoring' ? symbols[done % symbols.length] : null,
  };
  return run;
}

export function startRun(profileId: number): Run {
  findProfile(profileId);
  const existing = state.runs.find(
    (r) =>
      r.profile_id === profileId &&
      r.kind === 'full' &&
      (r.status === 'queued' || r.status === 'running'),
  );
  if (existing) return refreshRun(existing);
  const run: Run = {
    id: state.nextRunId++,
    profile_id: profileId,
    status: 'queued',
    kind: 'full',
    symbols: null,
    list_id: null,
    list_name: null,
    trading_day: null,
    progress: { phase: 'panel', done: 0, total: 0, current_symbol: null },
    universe_size: null,
    scored_size: null,
    passed_size: null,
    error: null,
    started_at: null,
    finished_at: null,
    created_at: new Date().toISOString(),
  };
  state.runs.unshift(run);
  runClocks.set(run.id, { startedMs: Date.now() });
  return run;
}

export function getRun(id: number): Run {
  const run = state.runs.find((r) => r.id === id) ?? fail(404, `Run ${id} not found`);
  return refreshRun(run);
}

export function listRuns(profileId: number, limit = 10): Run[] {
  findProfile(profileId);
  return state.runs
    .filter((r) => r.profile_id === profileId && r.kind === 'full')
    .map(refreshRun)
    .sort((a, b) => b.id - a.id)
    .slice(0, limit);
}

// ---------------------------------------------------------------- watchlist runs (My Picks)

const MAX_WATCHLIST = 50;
const DETAIL_ONLY = new Set([
  'trading_day',
  'decision',
  'reasons',
  'plan',
  'score_breakdown',
  'indicators',
  'fundamentals',
  'chart',
  'filters',
]);

function summaryOf(detail: SuggestionDetail): SuggestionSummary {
  return Object.fromEntries(
    Object.entries(detail).filter(([k]) => !DETAIL_ONLY.has(k)),
  ) as unknown as SuggestionSummary;
}

/** Scores one requested symbol and saves it as a `watchlist` suggestion (an unknown symbol gets an error row). */
function buildWatchlistItem(profile: Profile, symbol: string): WatchlistItem {
  const row = STOCK_ROWS.find((r) => r.symbol === symbol);
  if (!row) {
    // WatchlistMiss (contract "Watchlist runs"): exactly these ten fields.
    const miss: WatchlistMiss = {
      id: null,
      symbol,
      error: `${symbol} is not in the NSE universe for ${TRADING_DAY}.`,
      filters: null,
      score: null,
      signal: null,
      stage: null,
      price: null,
      is_tracked: false,
      position_id: null,
    };
    return miss;
  }
  const id = state.nextAdhocId++;
  const inList = suggestionsFor(profile).find((x) => x.symbol === symbol);
  const summary: SuggestionSummary = inList
    ? { ...inList, id, source: 'watchlist', rank: null }
    : { ...syntheticSummary(id, symbol, row.close, profile), source: 'watchlist' };
  const detail = buildDetail(summary, profile, !inList);
  state.adhoc.push({ profileId: profile.id, detail });
  return { ...summaryOf(detail), decision: detail.decision, filters: detail.filters, error: null };
}

/** Results grow as the run analyses symbols (in requested order), like the real backend. */
function ensureWatchlistItems(run: Run, count: number): WatchlistItem[] {
  const items = state.watchlistResults.get(run.id) ?? [];
  const profile = findProfile(run.profile_id);
  const symbols = run.symbols ?? [];
  while (items.length < Math.min(count, symbols.length))
    items.push(buildWatchlistItem(profile, symbols[items.length]));
  state.watchlistResults.set(run.id, items);
  return items;
}

function refreshWatchlistRun(run: Run): Run {
  const clock = runClocks.get(run.id);
  const elapsed = clock ? Date.now() - clock.startedMs : Infinity;
  if (elapsed < 600) return run;
  const symbols = run.symbols ?? [];
  const total = symbols.length;
  const duration = Math.min(12000, Math.max(3000, total * 700));
  const f = Math.min(1, (elapsed - 600) / duration);
  if (f >= 1) {
    const items = ensureWatchlistItems(run, total);
    Object.assign(run, {
      status: 'done',
      trading_day: TRADING_DAY,
      progress: { phase: 'done', done: total, total, current_symbol: null },
      universe_size: total,
      scored_size: items.filter((i) => i.error === null).length,
      passed_size: items.filter((i) => i.error === null && i.filters.passed).length,
      started_at: run.started_at ?? NOW_ISO,
      finished_at: new Date().toISOString(),
    });
    return run;
  }
  const phase = f < 0.1 ? 'panel' : f < 0.8 ? 'scoring' : f < 0.9 ? 'filtering' : 'planning';
  const done =
    phase === 'panel'
      ? 0
      : phase === 'scoring'
        ? Math.max(0, Math.min(total, Math.floor(((f - 0.1) / 0.7) * total)))
        : total;
  ensureWatchlistItems(run, done);
  run.status = 'running';
  run.started_at = run.started_at ?? new Date(clock?.startedMs ?? Date.now()).toISOString();
  run.trading_day = TRADING_DAY;
  run.progress = {
    phase,
    done,
    total,
    current_symbol: phase === 'scoring' ? (symbols[done] ?? null) : null,
  };
  return run;
}

export function startWatchlistRun(profileId: number, body: WatchlistRunBody): Run {
  findProfile(profileId);
  const hasList = body.list_id !== undefined && body.list_id !== null;
  const hasSymbols = body.symbols !== undefined && body.symbols !== null;
  if (hasList === hasSymbols) fail(400, 'Give exactly one of list_id or symbols');
  const list = hasList ? findPickList(body.list_id as number) : null;
  // A list run uses the list's current symbols; `symbols` is still stored so results stay readable later.
  const symbols = list ? [...list.symbols] : normalizeSymbols(body.symbols ?? []);
  const run: Run = {
    id: state.nextRunId++,
    profile_id: profileId,
    status: 'queued',
    kind: 'watchlist',
    symbols,
    list_id: list?.id ?? null,
    list_name: list?.name ?? null,
    trading_day: null,
    progress: { phase: 'panel', done: 0, total: symbols.length, current_symbol: null },
    universe_size: null,
    scored_size: null,
    passed_size: null,
    error: null,
    started_at: null,
    finished_at: null,
    created_at: new Date().toISOString(),
  };
  state.runs.unshift(run);
  runClocks.set(run.id, { startedMs: Date.now() });
  return run;
}

export function getRunResults(runId: number): WatchlistResults {
  const run = getRun(runId);
  if (run.kind !== 'watchlist')
    fail(400, `Run ${runId} is a full run; results exist only for watchlist runs`);
  const analysed = run.status === 'done' ? (run.symbols?.length ?? 0) : run.progress.done;
  const items = ensureWatchlistItems(run, analysed).map((item): WatchlistItem => {
    if (item.error !== null) return item; // a miss is never tracked
    const pos = isTracked(run.profile_id, item.symbol);
    const stored = state.adhoc.find((a) => a.detail.id === item.id);
    // "WatchlistHit gains analyst" (contract "The brain"); the TS block does not declare it yet.
    const hit: WithAnalyst<typeof item> = {
      ...item,
      is_tracked: !!pos,
      position_id: pos?.id ?? null,
      analyst: stored ? analystFor(stored.detail, run.profile_id) : null,
    };
    return hit;
  });
  return { run, items };
}

export function listWatchlistRuns(profileId: number, limit = 10, listId?: number): Run[] {
  findProfile(profileId);
  return state.runs
    .filter(
      (r) =>
        r.profile_id === profileId &&
        r.kind === 'watchlist' &&
        (listId === undefined || r.list_id === listId),
    )
    .map(refreshRun)
    .sort((a, b) => b.id - a.id)
    .slice(0, limit);
}

// ---------------------------------------------------------------- pick lists (named My Picks lists)

const MAX_LIST_NAME = 60;

/** Upper-cased, de-duplicated, order preserved; 1-50 entries (contract "Pick lists"). */
function normalizeSymbols(raw: string[]): string[] {
  const symbols = [...new Set(raw.map((x) => String(x).trim().toUpperCase()).filter(Boolean))];
  if (symbols.length === 0 || symbols.length > MAX_WATCHLIST)
    fail(400, `Give between 1 and ${MAX_WATCHLIST} symbols (got ${symbols.length})`);
  return symbols;
}

function normalizeName(raw: string | undefined, exceptId: number | null): string {
  const name = (raw ?? '').trim();
  if (name.length < 1 || name.length > MAX_LIST_NAME)
    fail(400, `A list name must be 1-${MAX_LIST_NAME} characters`);
  if (state.pickLists.some((l) => l.id !== exceptId && l.name.toLowerCase() === name.toLowerCase()))
    fail(409, `A list named "${name}" already exists`);
  return name;
}

function findPickList(id: number): PickList {
  return state.pickLists.find((l) => l.id === id) ?? fail(404, `Pick list ${id} not found`);
}

export function listPickLists(): PickList[] {
  return [...state.pickLists].sort(
    (a, b) => b.updated_at.localeCompare(a.updated_at) || b.id - a.id,
  );
}

export function createPickList(body: CreatePickListBody): PickList {
  const name = normalizeName(body.name, null);
  const symbols = normalizeSymbols(body.symbols ?? []);
  const now = new Date().toISOString();
  const list: PickList = {
    id: state.nextPickListId++,
    name,
    symbols,
    created_at: now,
    updated_at: now,
  };
  state.pickLists.push(list);
  return list;
}

export function updatePickList(id: number, body: UpdatePickListBody): PickList {
  const list = findPickList(id);
  const name = body.name !== undefined ? normalizeName(body.name, id) : list.name;
  const symbols = body.symbols !== undefined ? normalizeSymbols(body.symbols) : list.symbols;
  Object.assign(list, { name, symbols, updated_at: new Date().toISOString() });
  // list_name on runs is "name at read time".
  state.runs.forEach((r) => {
    if (r.list_id === id) r.list_name = name;
  });
  return list;
}

export function deletePickList(id: number): void {
  findPickList(id);
  state.pickLists = state.pickLists.filter((l) => l.id !== id);
  // Past runs are kept; they just lose the link.
  state.runs.forEach((r) => {
    if (r.list_id === id) Object.assign(r, { list_id: null, list_name: null });
  });
}

// ---------------------------------------------------------------- suggestions

export function getSuggestions(profileId: number, runId: number | 'latest'): SuggestionsResponse {
  const profile = findProfile(profileId);
  const runs = state.runs.filter((r) => r.profile_id === profileId).map(refreshRun);
  const run =
    runId === 'latest'
      ? (runs
          .filter((r) => r.kind === 'full' && r.status === 'done')
          .sort((a, b) => b.id - a.id)[0] ?? null)
      : (runs.find((r) => r.id === runId) ?? fail(404, `Run ${runId} not found`));
  return { run, items: run ? suggestionsFor(profile) : [] };
}

export function getSuggestionDetail(id: number): WithAnalyst<SuggestionDetail> {
  if (id >= ADHOC_ID_START) {
    const entry =
      state.adhoc.find((a) => a.detail.id === id) ?? fail(404, `Suggestion ${id} not found`);
    return withAnalyst(withTracking(entry), entry.profileId);
  }
  const profile = findProfile(Math.floor(id / 100));
  const item = suggestionsFor(profile).find((s) => s.id === id);
  const index = (id % 100) - 1;
  const fallback = SUGGESTION_SEEDS[index];
  if (!item && !fallback) fail(404, `Suggestion ${id} not found`);
  const summary: SuggestionSummary =
    item ??
    withVerdict(
      {
        ...fallback,
        id,
        source: 'run',
        rank: index + 1,
        risk_reward: riskReward(fallback),
        is_tracked: !!isTracked(profile.id, fallback.symbol),
        position_id: isTracked(profile.id, fallback.symbol)?.id ?? null,
      },
      profile,
      true,
    );
  return withAnalyst(buildDetail(summary, profile, false), profile.id);
}

// ---------------------------------------------------------------- stocks

const STOCK_ROWS: StockRow[] = UNIVERSE.map(([symbol, close]) => {
  const rand = seeded(`row:${symbol}`);
  const known = SUGGESTION_SEEDS.find((s) => s.symbol === symbol);
  return {
    symbol,
    close,
    change_1d_pct: round((rand() - 0.5) * 4, 1),
    change_1w_pct: round((rand() - 0.5) * 9, 1),
    change_1m_pct: known?.change_1m_pct ?? round((rand() - 0.45) * 22, 1),
    change_3m_pct: known?.change_3m_pct ?? round((rand() - 0.4) * 45, 1),
    dist_from_52w_high_pct: round(-rand() * 38, 1),
    volume_ratio_20d: known?.volume_ratio_20d ?? round(0.6 + rand() * 1.9, 1),
    avg_turnover_lacs: round(500 + rand() * 250000, 1),
  };
});

export function listStocks(q: StockQuery): StocksResponse {
  const search = (q.search ?? '').trim().toLowerCase();
  const sort = q.sort ?? 'change_1m_pct';
  const dir = (q.order ?? 'desc') === 'asc' ? 1 : -1;
  const prefix = (r: StockRow) => (search && r.symbol.toLowerCase().startsWith(search) ? 0 : 1);
  const rows = STOCK_ROWS.filter((r) => !search || r.symbol.toLowerCase().includes(search));
  rows.sort((a, b) => {
    const byPrefix = prefix(a) - prefix(b);
    if (byPrefix) return byPrefix;
    const av = a[sort],
      bv = b[sort];
    if (av === null && bv === null) return 0;
    if (av === null) return 1; // unavailable values always sort last
    if (bv === null) return -1;
    return typeof av === 'string' && typeof bv === 'string'
      ? dir * av.localeCompare(bv)
      : dir * (Number(av) - Number(bv));
  });
  const offset = q.offset ?? 0;
  return {
    trading_day: TRADING_DAY,
    total: rows.length,
    items: rows.slice(offset, offset + (q.limit ?? 50)),
  };
}

function findRow(symbol: string): StockRow {
  return (
    STOCK_ROWS.find((r) => r.symbol === symbol.toUpperCase()) ??
    fail(404, `${symbol} is not in the NSE universe`)
  );
}

export function getStock(symbol: string): StockDetail {
  const row = findRow(symbol);
  const chart = buildChart(row.symbol, row.close, row.change_3m_pct ?? 0);
  return {
    symbol: row.symbol,
    trading_day: TRADING_DAY,
    close: row.close,
    metrics: row,
    indicators: buildIndicators(row.symbol, row.close, chart, row.volume_ratio_20d),
    chart,
  };
}

function withTracking(entry: { profileId: number; detail: SuggestionDetail }): SuggestionDetail {
  const pos = isTracked(entry.profileId, entry.detail.symbol);
  return { ...entry.detail, is_tracked: !!pos, position_id: pos?.id ?? null };
}

export function analyzeStock(symbol: string, profileId: number): WithAnalyst<SuggestionDetail> {
  const profile = findProfile(profileId);
  const row = findRow(symbol);
  const existing = state.adhoc.find(
    (a) => a.profileId === profileId && a.detail.symbol === row.symbol,
  );
  const id = existing?.detail.id ?? state.nextAdhocId++;
  const inList = suggestionsFor(profile).find((s) => s.symbol === row.symbol);
  const summary: SuggestionSummary = inList
    ? { ...inList, id, source: 'explore', rank: null }
    : syntheticSummary(id, row.symbol, universeClose(row.symbol) ?? row.close, profile);
  const entry = { profileId, detail: buildDetail(summary, profile, !inList) };
  if (existing) existing.detail = entry.detail;
  else state.adhoc.push(entry);
  return withAnalyst(withTracking(entry), profileId);
}

// ---------------------------------------------------------------- the brain (evidence packs, analyst views)

function packFor(detail: SuggestionDetail): EvidencePack {
  const row = STOCK_ROWS.find((r) => r.symbol === detail.symbol);
  return brain.buildEvidencePack({
    s: detail,
    ind: detail.indicators,
    plan: detail.plan,
    change1w: row?.change_1w_pct ?? null,
    dist52w: row?.dist_from_52w_high_pct ?? null,
  });
}

function analystFor(detail: SuggestionDetail, profileId: number): AnalystView | null {
  return brain.viewFor(detail, detail.decision, packFor(detail), profileId);
}

function withAnalyst(detail: SuggestionDetail, profileId: number): WithAnalyst<SuggestionDetail> {
  return { ...detail, analyst: analystFor(detail, profileId) };
}

/** What the brain reasons over for a symbol under a strategy: the stored analysis, else the list entry, else a fresh score. */
function detailForSymbol(symbol: string, profileId: number): SuggestionDetail {
  const profile = findProfile(profileId);
  const row = findRow(symbol);
  const stored = state.adhoc.find(
    (a) => a.profileId === profileId && a.detail.symbol === row.symbol,
  );
  if (stored) return stored.detail;
  const inList = suggestionsFor(profile).find((s) => s.symbol === row.symbol);
  const summary =
    inList ?? syntheticSummary(0, row.symbol, universeClose(row.symbol) ?? row.close, profile);
  return buildDetail(summary, profile, !inList);
}

function requireBrainDay(day: string | undefined, what: string): void {
  if (day && day !== TRADING_DAY) fail(404, `No ${what} for ${day}`);
}

export function getEvidence(symbol: string, day?: string): EvidencePack {
  requireBrainDay(day, 'evidence pack');
  const row = findRow(symbol);
  if (!brain.isPackBuilt(row.symbol)) fail(404, `No evidence pack built for ${row.symbol}`);
  return packFor(detailForSymbol(row.symbol, getActiveProfile().id));
}

export function buildEvidence(symbol: string): EvidencePack {
  const row = findRow(symbol);
  brain.markPackBuilt(row.symbol);
  return packFor(detailForSymbol(row.symbol, getActiveProfile().id));
}

export function requestAnalystView(symbol: string, profileId: number): AnalystRunResult {
  const detail = detailForSymbol(symbol, profileId);
  return brain.requestView(detail, detail.decision, packFor(detail), profileId);
}

/** The contract's GET takes only `day`, so the mock answers for the active strategy (see "Proposed changes"). */
export function getAnalystView(symbol: string, day?: string): AnalystView {
  requireBrainDay(day, 'analyst view');
  const detail = detailForSymbol(symbol, getActiveProfile().id);
  return (
    analystFor(detail, getActiveProfile().id) ?? fail(404, `No analyst view for ${detail.symbol}`)
  );
}

// ---------------------------------------------------------------- positions

function findPosition(id: number): PositionDetail {
  return state.positions.find((p) => p.id === id) ?? fail(404, `Position ${id} not found`);
}

export function createPosition(body: CreatePositionBody): PositionDetail {
  const profile = findProfile(body.profile_id);
  let symbol = body.symbol?.toUpperCase();
  let summary: SuggestionSummary | null = null;
  if (body.suggestion_id !== undefined) {
    summary = getSuggestionDetail(body.suggestion_id);
    symbol = summary.symbol;
  }
  if (!symbol) fail(400, 'Provide suggestion_id or symbol');
  const row = findRow(symbol);
  if (isTracked(profile.id, symbol))
    fail(409, `${symbol} is already being tracked in this profile`);
  const capital = body.capital ?? Number(profile.params.paper_capital ?? 10000);
  const qty = Math.floor(capital / row.close);
  if (qty < 1) fail(400, `₹${capital} is not enough for one share of ${symbol} at ₹${row.close}`);
  const invested = round(qty * row.close, 2);
  const plannedExit =
    summary?.planned_exit_date ??
    shiftDays(TRADING_DAY, HORIZON_DAYS[String(profile.params.horizon)] ?? 50);
  const d: PositionDetail = {
    id: state.nextPositionId++,
    profile_id: profile.id,
    suggestion_id: body.suggestion_id ?? null,
    symbol,
    opened_on: TRADING_DAY,
    entry_price: row.close,
    qty,
    invested,
    capital,
    cash_left: round(capital - invested, 2),
    target: summary?.target ?? null,
    stop_loss: summary?.stop_loss ?? null,
    original_exit_date: plannedExit,
    planned_exit_date: plannedExit,
    status: 'open',
    last_mark_date: null,
    last_close: null,
    current_value: null,
    pnl: null,
    pnl_pct: null,
    days_held: 0,
    days_to_exit: null,
    closed_on: null,
    exit_price: null,
    close_reason: null,
    needs_review: false,
    stage: summary?.stage ?? null,
    signal: summary?.signal ?? null,
    marks: [],
    events: [],
    suggestion: summary ? { ...summary, is_tracked: true } : null,
    benchmark: { symbol: 'NIFTY 50', change_pct_since_open: 0 },
  };
  addEvent(d, {
    event_date: TRADING_DAY,
    event_type: 'open',
    old_exit_date: null,
    new_exit_date: plannedExit,
    reason: null,
    price: row.close,
  });
  state.positions.unshift(derive(d));
  return d;
}

export function listPositions(profileId: number, status: PositionFilter = 'all'): Position[] {
  findProfile(profileId);
  return state.positions
    .filter((p) => p.profile_id === profileId && (status === 'all' || p.status === status))
    .sort((a, b) => b.opened_on.localeCompare(a.opened_on) || b.id - a.id)
    .map(toPosition);
}

export const getPosition = (id: number): PositionDetail => findPosition(id);

function requireReason(reason: string | undefined): string {
  const text = reason?.trim();
  return text ? text : fail(400, 'A reason is required');
}
function requireOpen(p: PositionDetail): void {
  if (p.status === 'closed') fail(409, `${p.symbol} is already closed`);
}

function changeExit(
  id: number,
  body: ChangeExitBody,
  kind: Extract<EventType, 'extend' | 'shorten'>,
): PositionDetail {
  const p = findPosition(id);
  requireOpen(p);
  const reason = requireReason(body.reason);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(body.new_exit_date ?? ''))
    fail(400, 'new_exit_date must be YYYY-MM-DD');
  if (kind === 'extend' && body.new_exit_date <= p.planned_exit_date)
    fail(
      400,
      `New exit date must be after the current planned date (${formatDate(p.planned_exit_date)})`,
    );
  if (kind === 'shorten' && body.new_exit_date >= p.planned_exit_date)
    fail(
      400,
      `New exit date must be before the current planned date (${formatDate(p.planned_exit_date)})`,
    );
  addEvent(p, {
    event_date: TODAY,
    event_type: kind,
    old_exit_date: p.planned_exit_date,
    new_exit_date: body.new_exit_date,
    reason,
    price: p.last_close,
  });
  p.planned_exit_date = body.new_exit_date;
  if (kind === 'extend' && p.status === 'due') p.status = 'open';
  return derive(p);
}
export const extendPosition = (id: number, body: ChangeExitBody): PositionDetail =>
  changeExit(id, body, 'extend');
export const shortenPosition = (id: number, body: ChangeExitBody): PositionDetail =>
  changeExit(id, body, 'shorten');

export function closePosition(id: number, body: ClosePositionBody): PositionDetail {
  const p = findPosition(id);
  requireOpen(p);
  const reason = requireReason(body.reason);
  const exitPrice = p.last_close ?? p.entry_price;
  Object.assign(p, {
    status: 'closed',
    closed_on: TRADING_DAY,
    exit_price: exitPrice,
    close_reason: 'manual',
  });
  derive(p);
  p.needs_review = (p.pnl ?? 0) < 0;
  addEvent(p, {
    event_date: TODAY,
    event_type: 'close',
    old_exit_date: null,
    new_exit_date: null,
    reason,
    price: exitPrice,
  });
  return p;
}

export function addPositionNote(id: number, body: NoteBody): PositionDetail {
  const p = findPosition(id);
  const note = body.note?.trim();
  if (!note) fail(400, 'A note cannot be empty');
  addEvent(p, {
    event_date: TODAY,
    event_type: 'note',
    old_exit_date: null,
    new_exit_date: null,
    reason: note,
    price: p.last_close,
  });
  return p;
}

export function getProfileStats(profileId: number): ProfileStats {
  findProfile(profileId);
  const all = state.positions.filter((p) => p.profile_id === profileId);
  const closed = all.filter((p) => p.status === 'closed');
  const wins = closed.filter((p) => (p.pnl ?? 0) > 0);
  const losses = closed.filter((p) => (p.pnl ?? 0) < 0);
  const mean = (xs: number[]): number | null =>
    xs.length ? round(xs.reduce((a, b) => a + b, 0) / xs.length, 1) : null;
  const pct = (p: PositionDetail) => p.pnl_pct ?? 0;
  const byPnl = [...closed].sort((a, b) => pct(b) - pct(a));
  const closedBy: Record<CloseReason, number> = {
    target_hit: 0,
    stop_hit: 0,
    horizon_closed: 0,
    manual: 0,
  };
  closed.forEach((p) => {
    if (p.close_reason) closedBy[p.close_reason]++;
  });
  const extended = all.filter((p) => p.events.some((e) => e.event_type === 'extend'));
  let helped = 0,
    hurt = 0;
  extended
    .filter((p) => p.status === 'closed')
    .forEach((p) => {
      const atOriginal = [...p.marks].reverse().find((m) => m.mark_date <= p.original_exit_date);
      if (!atOriginal || p.pnl === null) return;
      if (p.pnl > atOriginal.pnl) helped++;
      else if (p.pnl < atOriginal.pnl) hurt++;
    });
  return {
    open: all.filter((p) => p.status === 'open').length,
    due: all.filter((p) => p.status === 'due').length,
    closed: closed.length,
    wins: wins.length,
    losses: losses.length,
    win_rate_pct: closed.length ? round((wins.length / closed.length) * 100, 1) : null,
    avg_pnl_pct: mean(closed.map(pct)),
    avg_win_pct: mean(wins.map(pct)),
    avg_loss_pct: mean(losses.map(pct)),
    // total = every position; realised = closed only; unrealised = open + due (contract, Resolved 2026-11-05).
    total_pnl: round(
      all.reduce((s, p) => s + (p.pnl ?? 0), 0),
      2,
    ),
    realised_pnl: round(
      closed.reduce((s, p) => s + (p.pnl ?? 0), 0),
      2,
    ),
    unrealised_pnl: round(
      all.filter((p) => p.status !== 'closed').reduce((s, p) => s + (p.pnl ?? 0), 0),
      2,
    ),
    total_invested: round(
      all.reduce((s, p) => s + p.invested, 0),
      2,
    ),
    best: byPnl.length ? { symbol: byPnl[0].symbol, pnl_pct: pct(byPnl[0]) } : null,
    worst: byPnl.length
      ? { symbol: byPnl[byPnl.length - 1].symbol, pnl_pct: pct(byPnl[byPnl.length - 1]) }
      : null,
    closed_by: closedBy,
    extensions: { count: extended.length, helped, hurt },
    pending_reviews: all.filter((p) => p.needs_review).length,
  };
}

// ---------------------------------------------------------------- loss reviews

export const listReviewTags = (): ReviewTag[] => REVIEW_TAGS;

const isLoss = (p: PositionDetail): boolean => p.status === 'closed' && (p.pnl ?? 0) < 0;

export function getLosses(profileId: number): LossesResponse {
  findProfile(profileId);
  const mine = state.positions.filter((p) => p.profile_id === profileId);
  const ids = new Set(mine.map((p) => p.id));
  return {
    pending: mine.filter((p) => isLoss(p) && p.needs_review).map(toPosition),
    reviewed: state.reviews.filter((r) => ids.has(r.position_id)).sort((a, b) => b.id - a.id),
  };
}

export function createReview(positionId: number, body: ReviewBody): Review {
  const p = findPosition(positionId);
  if (!isLoss(p)) fail(409, `${p.symbol} is not a closed losing position`);
  if (state.reviews.some((r) => r.position_id === positionId))
    fail(409, `${p.symbol} already has a review`);
  const review: Review = {
    id: state.nextReviewId++,
    position_id: p.id,
    symbol: p.symbol,
    pnl: p.pnl ?? 0,
    pnl_pct: p.pnl_pct ?? 0,
    closed_on: p.closed_on ?? TRADING_DAY,
    close_reason: p.close_reason ?? 'manual',
    reasons: body.reasons,
    mistakes: body.mistakes,
    lesson: body.lesson,
    algo_change: body.algo_change,
    reviewed_on: TODAY,
    created_at: new Date().toISOString(),
  };
  state.reviews.unshift(review);
  p.needs_review = false;
  return review;
}

export function updateReview(id: number, body: ReviewBody): Review {
  const review = state.reviews.find((r) => r.id === id) ?? fail(404, `Review ${id} not found`);
  Object.assign(review, {
    reasons: body.reasons,
    mistakes: body.mistakes,
    lesson: body.lesson,
    algo_change: body.algo_change,
  });
  return review;
}

export function getLossSummary(profileId: number): LossSummary {
  findProfile(profileId);
  const losses = state.positions.filter((p) => p.profile_id === profileId && isLoss(p));
  const ids = new Set(losses.map((p) => p.id));
  const reviews = state.reviews.filter((r) => ids.has(r.position_id));
  const by_tag = REVIEW_TAGS.map((t) => ({
    key: t.key,
    label: t.label,
    count: reviews.filter((r) => r.reasons.includes(t.key)).length,
  }))
    .filter((t) => t.count > 0)
    .sort((a, b) => b.count - a.count);
  const avg = losses.length
    ? round(losses.reduce((s, p) => s + (p.pnl_pct ?? 0), 0) / losses.length, 1)
    : null;
  return { total_losses: losses.length, reviewed: reviews.length, by_tag, avg_loss_pct: avg };
}

// ---------------------------------------------------------------- jobs

export function getJobStatus(): JobStatus {
  const { job } = state;
  const running = Date.now() < job.runningUntilMs;
  if (!running && job.status.running) {
    job.status = {
      ...job.status,
      running: false,
      last_daily_update: new Date().toISOString(),
      last_summary: {
        marked: state.positions.filter((p) => p.status !== 'closed').length,
        closed_target: 0,
        closed_stop: 0,
        marked_due: 0,
      },
    };
  }
  return { ...job.status, running };
}

export function triggerDailyUpdate(): DailyUpdateStarted {
  if (getJobStatus().running) return { started: false, reason: 'already running' };
  state.job.runningUntilMs = Date.now() + 2500;
  state.job.status = { ...state.job.status, running: true };
  return { started: true };
}
