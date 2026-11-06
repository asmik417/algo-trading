// Labels and colours for "The brain": analyst actions and confidence, market regimes, evidence states.
import type { AnalystAction, AnalystConfidence, Regime } from '../types/api';
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

export const CONFIDENCE_LABEL: Record<AnalystConfidence, string> = {
  low: 'Low confidence',
  medium: 'Medium confidence',
  high: 'High confidence',
};
export const CONFIDENCE_TONE: Record<AnalystConfidence, Tone> = {
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

// Evidence-pack `unavailable` names: sections ("ownership") and single fields in dotted form ("market.vix").
const SECTION_LABEL: Record<string, string> = {
  price: 'Price',
  quarters: 'Quarterly results',
  ownership: 'Shareholding',
  deals: 'Deals',
  events: 'Events',
  headlines: 'Headlines',
  market: 'Market',
  rules_verdict: 'Rules verdict',
  plan: 'Plan',
};
const FIELD_LABEL: Record<string, string> = {
  vs_nifty_1m_pct: 'vs Nifty, 1 month',
  vs_sector_1m_pct: 'vs sector, 1 month',
  dist_52w_high_pct: 'from 52-week high',
  delivery_pct_now: 'delivery now',
  delivery_pct_prev: 'delivery before',
  fii_pct: 'FIIs',
  dii_pct: 'DIIs',
  pledge_pct: 'pledged',
  vix: 'India VIX',
  fii_net_cr: 'FII net',
  dii_net_cr: 'DII net',
  sector_index: 'sector index',
  insider: 'insider deals',
};

/** "ownership" → "Shareholding"; "market.vix" → "Market: India VIX"; unknown names fall back to readable words. */
export function unavailableLabel(name: string): string {
  const words = (s: string) => s.replace(/_pct$/, '').replace(/_/g, ' ');
  const [section, field] = name.split('.', 2);
  const head = SECTION_LABEL[section] ?? words(section);
  return field === undefined ? head : `${head}: ${FIELD_LABEL[field] ?? words(field)}`;
}
