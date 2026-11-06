// Labels and colours for the three-part verdict (contract section "Verdict").
import type { Overall, Trend, Verdict } from '../types/api';
import type { Tone } from './colors';

export const OVERALL_LABEL: Record<Overall, string> = {
  buy: 'Buy',
  watch: 'Watch',
  avoid: 'Avoid',
};
export const OVERALL_TONE: Record<Overall, Tone> = {
  buy: 'green',
  watch: 'amber',
  avoid: 'greyRed',
};

/** Green at a full pass, amber at 1-2 failures, red above that. */
export function rulesTone(rules: Verdict['rules']): Tone {
  const failed = rules.failures.length;
  return failed === 0 ? 'green' : failed <= 2 ? 'amber' : 'red';
}

export const TREND_WORD: Record<Trend, string> = {
  uptrend: 'Uptrend',
  downtrend: 'Downtrend',
  sideways: 'Sideways',
};
