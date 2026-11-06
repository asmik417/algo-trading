// Labels and colours for "The brain": analyst actions and confidence, market regimes, evidence states.
import type { AnalystAction, Confidence, Regime } from '../types/brain';
import type { Tone } from './colors';

export const ACTION_LABEL: Record<AnalystAction, string> = {
  buy: 'Buy',
  watch: 'Watch',
  avoid: 'Avoid',
  add: 'Add',
  hold: 'Hold',
  trim: 'Trim',
  exit: 'Exit',
};
// Same colours as the rules verdict for buy / watch / avoid, so the two calls compare at a glance.
export const ACTION_TONE: Record<AnalystAction, Tone> = {
  buy: 'green',
  watch: 'amber',
  avoid: 'greyRed',
  add: 'green',
  hold: 'blue',
  trim: 'orange',
  exit: 'red',
};

export const CONFIDENCE_LABEL: Record<Confidence, string> = {
  low: 'Low confidence',
  medium: 'Medium confidence',
  high: 'High confidence',
};
export const CONFIDENCE_TONE: Record<Confidence, Tone> = {
  low: 'grey',
  medium: 'blue',
  high: 'green',
};

export const REGIME_LABEL: Record<Regime, string> = {
  risk_on: 'Risk on',
  neutral: 'Neutral',
  risk_off: 'Risk off',
};
export const REGIME_TONE: Record<Regime, Tone> = {
  risk_on: 'green',
  neutral: 'amber',
  risk_off: 'red',
};

export const EVIDENCE_LABEL: Record<'present' | 'absent' | 'unknown', string> = {
  present: 'Present',
  absent: 'Absent',
  unknown: 'Unknown',
};
export const EVIDENCE_TONE: Record<'present' | 'absent' | 'unknown', Tone> = {
  present: 'green',
  absent: 'red',
  unknown: 'grey',
};
