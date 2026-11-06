// Plain-English labels and help for backtest settings, phases and exits (contract "Backtests").
import type {
  Backtest,
  BacktestExit,
  EntryRule,
  FundamentalsMode,
  ScanFrequency,
} from '../types/api';
import { formatNumber } from './format';
import type { Tone } from './colors';
import { CLOSE_REASON_LABEL, CLOSE_REASON_TONE } from './labels';

export const BACKTEST_PHASES: Record<string, string> = {
  history: 'Loading price history',
  fundamentals: 'Fetching fundamentals',
  scanning: 'Scanning',
  simulating: 'Simulating trades',
  saving: 'Saving results',
  done: 'Finishing',
};

export const FREQUENCY_LABEL: Record<ScanFrequency, string> = { weekly: 'Weekly', daily: 'Daily' };
export const FREQUENCY_HELP: Record<ScanFrequency, string> = {
  weekly: 'Scan on the last trading day of each week.',
  daily: 'Scan every trading day (slower, many more picks).',
};

export const ENTRY_RULE_LABEL: Record<EntryRule, string> = {
  next_close: 'Next close',
  optimal_limit: 'Optimal limit',
};
export const ENTRY_RULE_HELP: Record<EntryRule, string> = {
  next_close: 'Buy at the close of the next trading day, like pressing Track the next evening.',
  optimal_limit:
    'Buy at the optimal entry if the price dips to it within 5 sessions; otherwise no trade.',
};

export const FUNDAMENTALS_LABEL: Record<FundamentalsMode, string> = {
  point_in_time: 'Point in time',
  technical_only: 'Technical only',
};
export const FUNDAMENTALS_HELP: Record<FundamentalsMode, string> = {
  point_in_time:
    "Use only results published by each scan date (some ratios are today's values; see caveats).",
  technical_only:
    'Ignore fundamentals: earnings, quality and valuation weights are 0 and those rules are skipped.',
};

export const EXIT_LABEL: Record<BacktestExit, string> = {
  ...CLOSE_REASON_LABEL,
  open: 'Open at end',
};
export const EXIT_TONE: Record<BacktestExit, Tone> = { ...CLOSE_REASON_TONE, open: 'blue' };

/** "Weekly · Next close · Point in time · cost 0.30 %" */
export const settingsLine = (b: Backtest): string =>
  `${FREQUENCY_LABEL[b.frequency]} · ${ENTRY_RULE_LABEL[b.entry_rule]} · ${FUNDAMENTALS_LABEL[b.fundamentals_mode]} · cost ${formatNumber(b.cost_pct, 2)} %`;
