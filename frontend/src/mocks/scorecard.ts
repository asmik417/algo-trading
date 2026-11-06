// Mock of the verdict log and scorecard (contract "The brain", Verdict log and scorecard).
// Each strategy gets a fixed, seeded log; marks come from one price series per symbol, so they agree with each other.
import type {
  ChartData,
  Direction,
  AnalystAction,
  LoggedVerdict,
  Scorecard,
  ScorecardRow,
  VerdictSource,
} from '../types/api';
import { buildChart } from './chart';
import { round, seeded } from './dates';
import { getProfile } from './db';
import { SUGGESTION_SEEDS, UNIVERSE } from './fixtures';
import { fail } from './respond';

export const HORIZONS = [20, 40, 60] as const;
type Horizon = (typeof HORIZONS)[number];

/** Verdicts logged per strategy: #1 has 60 across both sources, #2 a few, #3 none (empty state). */
const LOG_SIZE: Record<number, { rules: number; analyst: number }> = {
  1: { rules: 34, analyst: 26 },
  2: { rules: 10, analyst: 8 },
};
const HISTORY_SESSIONS = 220;
const SIGNALS = [
  '🟢 Early Setup',
  '🟡 Developing',
  '🔵 Breakout Confirmed',
  '🟠 Extended',
  '🔴 Weak / Invalidated',
];

/** by_signal's key for verdicts with no rules signal that day (contract "Verdict log and scorecard"). */
export const NO_SIGNAL = 'No signal';

const series = new Map<string, ChartData>();
function seriesFor(symbol: string, close: number): ChartData {
  let s = series.get(symbol);
  if (!s) {
    s = buildChart(`score:${symbol}`, close, 0, HISTORY_SESSIONS);
    series.set(symbol, s);
  }
  return s;
}

/** right when the change matches the direction: up > 0, down < 0, sideways within ±5 %. */
export const isRight = (direction: Direction, changePct: number): boolean =>
  direction === 'up'
    ? changePct > 0
    : direction === 'down'
      ? changePct < 0
      : Math.abs(changePct) <= 5;

const DIRECTION_OF: Record<AnalystAction, Direction[]> = {
  buy: ['up'],
  add: ['up'],
  watch: ['sideways'],
  hold: ['sideways'],
  avoid: ['down', 'sideways'],
  trim: ['down'],
  exit: ['down'],
};

function pickAction(
  source: VerdictSource,
  rand: () => number,
  futureChange: number | null,
): AnalystAction {
  // The analyst sometimes reads the tape right (that is what the scorecard is meant to reveal).
  if (source === 'analyst' && futureChange !== null && rand() < 0.35)
    return futureChange > 4 ? 'buy' : futureChange < -4 ? 'avoid' : 'watch';
  const r = rand();
  if (source === 'analyst' && r > 0.92) return r > 0.96 ? 'trim' : 'hold';
  return r < 0.45 ? 'buy' : r < 0.8 ? 'watch' : 'avoid';
}

const logs = new Map<number, LoggedVerdict[]>();

function buildLog(profileId: number): LoggedVerdict[] {
  const size = LOG_SIZE[profileId] ?? { rules: 0, analyst: 0 };
  const rand = seeded(`verdict-log:${profileId}`);
  const symbols: [string, number, string | null][] = [
    ...SUGGESTION_SEEDS.map((s): [string, number, string | null] => [s.symbol, s.price, s.signal]),
    ...UNIVERSE.slice(0, 24).map(([sym, close]): [string, number, string | null] => [
      sym,
      close,
      null,
    ]),
  ];
  const seen = new Set<string>();
  const out: LoggedVerdict[] = [];
  const sources: VerdictSource[] = [
    ...Array<VerdictSource>(size.rules).fill('rules'),
    ...Array<VerdictSource>(size.analyst).fill('analyst'),
  ];
  for (const source of sources) {
    for (let tries = 0; tries < 50; tries++) {
      const [symbol, close, knownSignal] = symbols[Math.floor(rand() * symbols.length)];
      const s = seriesFor(symbol, close);
      const i = Math.floor(rand() * s.dates.length);
      const key = `${symbol}:${s.dates[i]}:${source}`;
      if (seen.has(key)) continue;
      seen.add(key);
      const c0 = s.close[i];
      const future = s.close[i + 20];
      const action = pickAction(
        source,
        rand,
        future === undefined ? null : (future / c0 - 1) * 100,
      );
      const dirs = DIRECTION_OF[action];
      const direction = dirs[Math.floor(rand() * dirs.length)];
      const marks = HORIZONS.filter((n) => i + n < s.dates.length).map((sessions) => {
        const c = s.close[i + sessions];
        const change_pct = round((c / c0 - 1) * 100, 1);
        return {
          sessions,
          date: s.dates[i + sessions],
          close: c,
          change_pct,
          right: isRight(direction, change_pct),
        };
      });
      // The rules signal of that symbol on that day; some analyst views had no rules verdict that day.
      const signal =
        source === 'analyst' && rand() < 0.2
          ? null
          : (knownSignal ?? SIGNALS[Math.floor(rand() * SIGNALS.length)]);
      out.push({
        id: profileId * 1000 + out.length + 1,
        symbol,
        day: s.dates[i],
        source,
        profile_id: profileId,
        action,
        direction,
        level:
          direction === 'up'
            ? round(c0 * 1.12, 2)
            : direction === 'down'
              ? round(c0 * 0.93, 2)
              : null,
        close: c0,
        signal,
        marks,
      });
      break;
    }
  }
  return out.sort((a, b) => b.day.localeCompare(a.day) || b.id - a.id);
}

function logFor(profileId: number): LoggedVerdict[] {
  let log = logs.get(profileId);
  if (!log) {
    log = buildLog(profileId);
    logs.set(profileId, log);
  }
  return log;
}

const markAt = (v: LoggedVerdict, horizon: Horizon) => v.marks.find((m) => m.sessions === horizon);

function rowOf(key: string, verdicts: LoggedVerdict[], horizon: Horizon): ScorecardRow {
  const marked = verdicts.flatMap((v) => {
    const m = markAt(v, horizon);
    return m ? [{ v, m }] : [];
  });
  const right = marked.filter((x) => x.m.right).length;
  // avg_change_pct is the edge: change in the call's direction (up → change, down → −change), sideways excluded.
  const edges = marked
    .filter((x) => x.v.direction !== 'sideways')
    .map((x) => (x.v.direction === 'up' ? x.m.change_pct : -x.m.change_pct));
  return {
    key,
    verdicts: verdicts.length,
    marked: marked.length,
    right,
    hit_rate_pct: marked.length ? round((right / marked.length) * 100, 1) : null,
    avg_change_pct: edges.length ? round(edges.reduce((a, e) => a + e, 0) / edges.length, 1) : null,
  };
}

function groupRows(
  entries: LoggedVerdict[],
  keyOf: (v: LoggedVerdict) => string,
  order: string[],
  horizon: Horizon,
): ScorecardRow[] {
  const groups = new Map<string, LoggedVerdict[]>();
  for (const e of entries) groups.set(keyOf(e), [...(groups.get(keyOf(e)) ?? []), e]);
  const keys = [...groups.keys()].sort((a, b) => {
    const ia = order.indexOf(a),
      ib = order.indexOf(b);
    return ia === -1 && ib === -1
      ? a.localeCompare(b)
      : (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
  });
  return keys.map((k) => rowOf(k, groups.get(k) ?? [], horizon));
}

/** How far a wrong mark went against the call (bigger = worse miss). */
function missSize(v: LoggedVerdict, change: number): number {
  if (v.direction === 'up') return -change;
  if (v.direction === 'down') return change;
  return Math.abs(change) - 5;
}

const ACTION_ORDER: AnalystAction[] = ['buy', 'add', 'watch', 'hold', 'avoid', 'trim', 'exit'];

export function getScorecard(profileId: number, source: string, horizon: number): Scorecard {
  getProfile(profileId); // 404 for an unknown strategy
  if (source !== 'rules' && source !== 'analyst' && source !== 'both')
    fail(422, 'source must be rules, analyst or both');
  if (!HORIZONS.includes(horizon as Horizon)) fail(422, 'horizon must be 20, 40 or 60');
  const h = horizon as Horizon;
  const entries = logFor(profileId).filter((v) => source === 'both' || v.source === source);
  const worst = entries
    .map((v) => ({ v, m: markAt(v, h) }))
    .filter((x) => x.m !== undefined && !x.m.right)
    .sort((a, b) => missSize(b.v, b.m?.change_pct ?? 0) - missSize(a.v, a.m?.change_pct ?? 0))
    .slice(0, 10)
    .map((x) => x.v);
  return {
    profile_id: profileId,
    source: source as Scorecard['source'],
    horizon: h,
    total: rowOf('total', entries, h),
    by_source: groupRows(entries, (v) => v.source, ['rules', 'analyst'], h),
    by_action: groupRows(entries, (v) => v.action, ACTION_ORDER, h),
    by_signal: groupRows(entries, (v) => v.signal ?? NO_SIGNAL, [...SIGNALS, NO_SIGNAL], h),
    by_month: groupRows(entries, (v) => v.day.slice(0, 7), [], h),
    worst,
  };
}
