// Mock of /backtests (contract "Backtests"): a deterministic simulated trade list per backtest, with the contract's
// summary maths, breakdowns, equity curve, drawdown and loss-pattern tagging, so mock mode behaves like the server.
import type {
  Backtest,
  BacktestBody,
  BacktestBreakdownRow,
  BacktestExit,
  BacktestLossPattern,
  BacktestResults,
  BacktestSummary,
  BacktestTrade,
  EquityPoint,
} from '../types/api';
import {
  NOW_ISO,
  TRADING_DAY,
  daysBetween,
  round,
  seeded,
  shiftDays,
  weekdaysBetween,
} from './dates';
import { getProfile } from './db';
import { REVIEW_TAGS, UNIVERSE } from './fixtures';
import { fail } from './respond';

const SIGNALS = ['🟢 Early Setup', '🟡 Developing', '🔵 Breakout Confirmed'];
const STAGES = ['Quiet Accumulation', 'Volume Expansion', 'Breakout', 'Momentum'];
const SECTORS = [
  'Technology',
  'Financial Services',
  'Industrials',
  'Healthcare',
  'Consumer Cyclical',
  'Energy',
  'Basic Materials',
];
const CAVEATS = [
  'Fundamentals are one snapshot per stock fetched today. Quarterly and cash-flow rows are dropped if their period ended within 45 days before (or after) the scan date, as if not yet published.',
  "ROE, debt/equity, profit margin, operating margin and revenue growth are today's values, not the values at each scan date.",
  'Stocks with no fundamentals today (e.g. delisted since) cannot be scored, so they never appear: survivorship bias.',
  'Fills are at closing prices (next close, or the optimal-entry limit); costs are a flat round-trip percentage; no slippage or partial fills.',
];
const TECHNICAL_CAVEAT =
  'Technical only: earnings, fundamental-quality and valuation weights are 0 and the P/E, ROE, debt, profit-growth and market-cap rules are skipped.';
const TAG_LABEL = new Map(REVIEW_TAGS.map((t) => [t.key, t.label]));
const PHASES = ['history', 'fundamentals', 'scanning', 'simulating', 'saving'] as const;
const DURATION_MS = 9000;

interface MockBacktestState {
  backtests: Backtest[];
  results: Map<number, BacktestResults>;
  clocks: Map<number, number>;
  nextId: number;
}

const state: MockBacktestState = {
  backtests: [],
  results: new Map(),
  clocks: new Map(),
  nextId: 2,
};

/** Last trading day of each ISO week (weekly) or every trading day (daily). */
function scanDates(start: string, end: string, frequency: Backtest['frequency']): string[] {
  const days = weekdaysBetween(start, end);
  if (frequency === 'daily') return days;
  return days.filter(
    (d, i) =>
      i === days.length - 1 ||
      new Date(`${days[i + 1]}T00:00:00`).getDay() < new Date(`${d}T00:00:00`).getDay(),
  );
}

function simulate(bt: Backtest): BacktestResults {
  const rand = seeded(
    `backtest:${bt.id}:${bt.profile_id}:${bt.start_date}:${bt.end_date}:${bt.entry_rule}:${bt.fundamentals_mode}`,
  );
  const scans = scanDates(bt.start_date, bt.end_date, bt.frequency);
  const symbols = UNIVERSE.map(([s, close]) => ({ s, close }));
  const openUntil = new Map<string, string>(); // symbol -> exit date of its open simulated trade
  const trades: BacktestTrade[] = [];
  let skippedRepeat = 0;
  let skippedNoFill = 0;
  let id = 1;

  scans.forEach((scan, scanIndex) => {
    const picks = Math.floor(rand() * (bt.frequency === 'daily' ? 2 : 5));
    for (let k = 0; k < picks; k++) {
      const { s, close } = symbols[Math.floor(rand() * symbols.length)];
      if (scanIndex === scans.length - 1) {
        skippedNoFill++;
        continue;
      }
      const busy = openUntil.get(s);
      if (busy && busy > scan) {
        skippedRepeat++;
        continue;
      }
      if (bt.entry_rule === 'optimal_limit' && rand() < 0.25) {
        skippedNoFill++;
        continue;
      }
      const entryDate = shiftDays(scan, new Date(`${scan}T00:00:00`).getDay() === 5 ? 3 : 1);
      const entry = round(close * (0.7 + rand() * 0.5), 2);
      const qty = Math.floor(bt.capital_per_trade / entry);
      if (qty < 1) {
        skippedNoFill++;
        continue;
      }
      const stop = round(entry * (0.86 + rand() * 0.08), 2);
      const target = round(entry * (1.12 + rand() * 0.14), 2);
      const planned = shiftDays(entryDate, 28 + Math.floor(rand() * 28));
      const roll = rand();
      let exitReason: BacktestExit;
      let exitPrice: number;
      let exitDate: string | null;
      if (planned > bt.end_date && roll > 0.4) {
        exitReason = 'open';
        exitPrice = round(entry * (0.92 + rand() * 0.18), 2);
        exitDate = null;
      } else if (roll < 0.14) {
        exitReason = 'target_hit';
        exitPrice = round(target * (1 + rand() * 0.02), 2);
        exitDate = shiftDays(entryDate, 6 + Math.floor(rand() * 20));
      } else if (roll < 0.42) {
        exitReason = 'stop_hit';
        exitPrice = round(stop * (0.98 + rand() * 0.02), 2);
        exitDate = shiftDays(entryDate, 2 + Math.floor(rand() * 18));
      } else {
        exitReason = 'horizon_closed';
        exitPrice = round(entry * (0.9 + rand() * 0.24), 2);
        exitDate = planned;
      }
      if (exitDate && exitDate > bt.end_date) exitDate = bt.end_date;
      const invested = round(qty * entry, 2);
      const markPrice = exitPrice;
      const pnl = round(qty * (markPrice - entry) - (invested * bt.cost_pct) / 100, 2);
      const pnlPct = round((pnl / invested) * 100, 2);
      const move = ((markPrice - entry) / entry) * 100;
      const daysHeld = daysBetween(entryDate, exitDate ?? bt.end_date);
      const mfe = round(Math.max(0, move) + rand() * 4, 2);
      const mae = round(Math.min(0, move) - rand() * 4, 2);
      const nifty = round(-6 + rand() * 11, 2);
      const price = entry;
      const cap = price > 2000 ? 'Large Cap' : price > 300 ? 'Mid Cap' : 'Small Cap';
      const tags: string[] = [];
      if (exitReason !== 'open' && pnl < 0) {
        if (exitReason === 'stop_hit' && daysHeld <= 7 && rand() < 0.5) tags.push('stop_too_tight');
        if (rand() < 0.12) tags.push('bought_extended');
        if (nifty <= -3) tags.push('whole_market_fell');
        if (exitReason === 'horizon_closed' && mfe >= ((target - entry) / entry) * 50)
          tags.push('held_too_long');
        if (rand() < 0.1) tags.push('bad_entry_timing');
        if (cap === 'Small Cap' && rand() < 0.3) tags.push('low_liquidity');
        if (tags.length === 0) tags.push('other');
      }
      trades.push({
        id: id++,
        symbol: s,
        scan_date: scan,
        entry_date: entryDate,
        entry_price: entry,
        qty,
        invested,
        stop_loss: stop,
        target,
        planned_exit_date: planned,
        signal: SIGNALS[Math.floor(rand() * SIGNALS.length)],
        stage: STAGES[Math.floor(rand() * STAGES.length)],
        score: round(62 + rand() * 26, 2),
        market_cap_bucket: cap,
        sector: rand() < 0.05 ? null : SECTORS[Math.floor(rand() * SECTORS.length)],
        exit_date: exitDate,
        exit_price: exitReason === 'open' ? null : exitPrice,
        exit_reason: exitReason,
        pnl,
        pnl_pct: pnlPct,
        r_multiple: entry === stop ? null : round((markPrice - entry) / (entry - stop), 2),
        days_held: daysHeld,
        mfe_pct: mfe,
        mae_pct: mae,
        nifty_pct: nifty,
        tags,
      });
      openUntil.set(s, exitDate ?? '9999-12-31');
    }
  });

  const closed = trades.filter((t) => t.exit_reason !== 'open');
  const wins = closed.filter((t) => t.pnl > 0);
  const losses = closed.filter((t) => t.pnl < 0);
  const mean = (xs: number[]) =>
    xs.length ? round(xs.reduce((a, b) => a + b, 0) / xs.length, 2) : null;
  const grossWin = wins.reduce((a, t) => a + t.pnl, 0);
  const grossLoss = -losses.reduce((a, t) => a + t.pnl, 0);

  // Equity curve: cumulative closed P&L by exit date; drawdown as % of capital × 10.
  const byExit = new Map<string, number>();
  closed.forEach((t) =>
    byExit.set(t.exit_date as string, (byExit.get(t.exit_date as string) ?? 0) + t.pnl),
  );
  let cum = 0;
  let peak = 0;
  let maxDd = 0;
  const equity: EquityPoint[] = [...byExit.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, pnl]) => {
      cum += pnl;
      peak = Math.max(peak, cum);
      maxDd = Math.max(maxDd, peak - cum);
      return { date, pnl: round(cum, 2) };
    });

  const summary: BacktestSummary = {
    trades: trades.length,
    closed: closed.length,
    wins: wins.length,
    losses: losses.length,
    open_at_end: trades.length - closed.length,
    skipped_repeat: skippedRepeat,
    skipped_no_fill: skippedNoFill,
    win_rate_pct: closed.length ? round((wins.length / closed.length) * 100, 2) : null,
    avg_win_pct: mean(wins.map((t) => t.pnl_pct)),
    avg_loss_pct: mean(losses.map((t) => t.pnl_pct)),
    avg_pnl_pct: mean(closed.map((t) => t.pnl_pct)),
    expectancy_r: mean(closed.map((t) => t.r_multiple).filter((r): r is number => r !== null)),
    profit_factor: grossLoss > 0 ? round(grossWin / grossLoss, 2) : null,
    total_pnl: round(
      trades.reduce((a, t) => a + t.pnl, 0),
      2,
    ),
    max_drawdown_pct: equity.length ? round((maxDd / (bt.capital_per_trade * 10)) * 100, 2) : null,
    avg_days_held: mean(closed.map((t) => t.days_held)),
    nifty_avg_pct: mean(closed.map((t) => t.nifty_pct).filter((n): n is number => n !== null)),
    exits: {
      target_hit: closed.filter((t) => t.exit_reason === 'target_hit').length,
      stop_hit: closed.filter((t) => t.exit_reason === 'stop_hit').length,
      horizon_closed: closed.filter((t) => t.exit_reason === 'horizon_closed').length,
      open: trades.length - closed.length,
    },
  };

  const breakdown = (keyOf: (t: BacktestTrade) => string): BacktestBreakdownRow[] => {
    const groups = new Map<string, BacktestTrade[]>();
    trades.forEach((t) => groups.set(keyOf(t), [...(groups.get(keyOf(t)) ?? []), t]));
    return [...groups.entries()]
      .map(([key, ts]) => {
        const c = ts.filter((t) => t.exit_reason !== 'open');
        return {
          key,
          trades: ts.length,
          win_rate_pct: c.length
            ? round((c.filter((t) => t.pnl > 0).length / c.length) * 100, 2)
            : null,
          avg_pnl_pct: mean(c.map((t) => t.pnl_pct)),
          total_pnl: round(
            ts.reduce((a, t) => a + t.pnl, 0),
            2,
          ),
        };
      })
      .sort((a, b) => b.trades - a.trades);
  };

  const tagCounts = new Map<string, number>();
  losses.forEach((t) => t.tags.forEach((g) => tagCounts.set(g, (tagCounts.get(g) ?? 0) + 1)));
  const lossPatterns: BacktestLossPattern[] = [...tagCounts.entries()]
    .map(([key, count]) => ({
      key,
      label: TAG_LABEL.get(key) ?? key,
      count,
      share_pct: round((count / Math.max(1, losses.length)) * 100, 2),
    }))
    .sort((a, b) => b.count - a.count);

  Object.assign(bt, {
    scan_count: scans.length,
    summary,
    caveats:
      bt.fundamentals_mode === 'technical_only' ? [TECHNICAL_CAVEAT, ...CAVEATS.slice(2)] : CAVEATS,
  });
  return {
    backtest: bt,
    by_signal: breakdown((t) => t.signal),
    by_stage: breakdown((t) => t.stage),
    by_market_cap: breakdown((t) => t.market_cap_bucket),
    by_sector: breakdown((t) => t.sector ?? 'Unknown'),
    by_month: breakdown((t) => t.entry_date.slice(0, 7)).sort((a, b) => a.key.localeCompare(b.key)),
    loss_patterns: lossPatterns,
    equity_curve: equity,
    trades,
  };
}

function newBacktest(
  id: number,
  body: Required<Omit<BacktestBody, 'capital_per_trade'>> & { capital_per_trade: number },
  done: boolean,
): Backtest {
  const profile = getProfile(body.profile_id);
  return {
    id,
    profile_id: profile.id,
    profile_name: profile.name,
    status: done ? 'done' : 'queued',
    start_date: body.start_date,
    end_date: body.end_date,
    frequency: body.frequency,
    entry_rule: body.entry_rule,
    fundamentals_mode: body.fundamentals_mode,
    cost_pct: body.cost_pct,
    capital_per_trade: body.capital_per_trade,
    params: { ...profile.params },
    progress: { phase: done ? 'done' : 'history', done: 0, total: 0, current_symbol: null },
    scan_count: null,
    summary: null,
    caveats: [],
    error: null,
    started_at: done ? NOW_ISO : null,
    finished_at: done ? NOW_ISO : null,
    created_at: done ? '2026-11-05T06:00:00Z' : new Date().toISOString(),
  };
}

function ensureSeeded(): void {
  if (state.backtests.length || state.results.size) return;
  const bt = newBacktest(
    1,
    {
      profile_id: 1,
      start_date: shiftDays(TRADING_DAY, -365),
      end_date: TRADING_DAY,
      frequency: 'weekly',
      entry_rule: 'next_close',
      fundamentals_mode: 'point_in_time',
      cost_pct: 0.3,
      capital_per_trade: 10000,
    },
    true,
  );
  state.backtests.push(bt);
  state.results.set(bt.id, simulate(bt));
}

function refresh(bt: Backtest): Backtest {
  if (bt.status === 'done' || bt.status === 'failed') return bt;
  const started = state.clocks.get(bt.id) ?? Date.now();
  const elapsed = Date.now() - started;
  if (elapsed < 600) return bt;
  const f = Math.min(1, (elapsed - 600) / DURATION_MS);
  const scans = scanDates(bt.start_date, bt.end_date, bt.frequency);
  if (f >= 1) {
    state.results.set(bt.id, simulate(bt));
    Object.assign(bt, {
      status: 'done',
      progress: { phase: 'done', done: scans.length, total: scans.length, current_symbol: null },
      finished_at: new Date().toISOString(),
    });
    return bt;
  }
  const phase =
    f < 0.1
      ? PHASES[0]
      : f < 0.25
        ? PHASES[1]
        : f < 0.8
          ? PHASES[2]
          : f < 0.95
            ? PHASES[3]
            : PHASES[4];
  const done =
    phase === 'scanning'
      ? Math.floor(((f - 0.25) / 0.55) * scans.length)
      : phase === 'history' || phase === 'fundamentals'
        ? 0
        : scans.length;
  Object.assign(bt, {
    status: 'running',
    started_at: bt.started_at ?? new Date(started).toISOString(),
    progress: {
      phase,
      done,
      total: scans.length,
      current_symbol: phase === 'scanning' ? (scans[done] ?? null) : null,
    },
  });
  return bt;
}

const find = (id: number): Backtest => {
  ensureSeeded();
  return state.backtests.find((b) => b.id === id) ?? fail(404, `Backtest ${id} not found`);
};

export function listBacktests(profileId?: number, limit = 20): Backtest[] {
  ensureSeeded();
  return state.backtests
    .filter((b) => profileId === undefined || b.profile_id === profileId)
    .map(refresh)
    .sort((a, b) => b.id - a.id)
    .slice(0, limit);
}

export const getBacktest = (id: number): Backtest => refresh(find(id));

export function getBacktestResults(id: number): BacktestResults {
  const bt = refresh(find(id));
  if (bt.status !== 'done') fail(409, `Backtest ${id} is not finished yet`);
  return state.results.get(id) as BacktestResults;
}

export function createBacktest(body: BacktestBody): Backtest {
  ensureSeeded();
  const profile = getProfile(body.profile_id);
  const busy = state.backtests
    .map(refresh)
    .find((b) => b.status === 'queued' || b.status === 'running');
  if (busy) fail(409, 'A backtest is already running');
  const iso = /^\d{4}-\d{2}-\d{2}$/;
  if (!iso.test(body.start_date ?? '') || !iso.test(body.end_date ?? ''))
    fail(400, 'start_date and end_date must be YYYY-MM-DD');
  if (body.start_date >= body.end_date) fail(400, 'start_date must be before end_date');
  if (body.end_date > TRADING_DAY)
    fail(400, `end_date must be on or before the last trading day (${TRADING_DAY})`);
  if (daysBetween(body.start_date, body.end_date) > 3 * 366)
    fail(400, 'A backtest can cover at most 3 years');
  const cost = body.cost_pct ?? 0.3;
  if (cost < 0 || cost > 5) fail(400, 'cost_pct must be between 0 and 5');
  const bt = newBacktest(
    state.nextId++,
    {
      profile_id: profile.id,
      start_date: body.start_date,
      end_date: body.end_date,
      frequency: body.frequency ?? 'weekly',
      entry_rule: body.entry_rule ?? 'next_close',
      fundamentals_mode: body.fundamentals_mode ?? 'point_in_time',
      cost_pct: cost,
      capital_per_trade: body.capital_per_trade ?? Number(profile.params.paper_capital ?? 10000),
    },
    false,
  );
  state.backtests.push(bt);
  state.clocks.set(bt.id, Date.now());
  return bt;
}

export function deleteBacktest(id: number): void {
  const bt = refresh(find(id));
  if (bt.status === 'queued' || bt.status === 'running')
    fail(409, 'A running backtest cannot be deleted');
  state.backtests = state.backtests.filter((b) => b.id !== id);
  state.results.delete(id);
}
