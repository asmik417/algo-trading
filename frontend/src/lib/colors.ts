// Colours for badges and signed numbers. Signal strings are matched on their label text (see "Enumerations" in the contract).
export type Tone = 'green' | 'amber' | 'blue' | 'orange' | 'red' | 'grey' | 'greyRed';

export const TONE_CLASSES: Record<Tone, string> = {
  green: 'bg-brand-soft text-brand-dark',
  amber: 'bg-amber-100 text-amber-800',
  blue: 'bg-blue-100 text-blue-800',
  orange: 'bg-orange-100 text-orange-800',
  red: 'bg-loss-soft text-loss',
  grey: 'bg-slate-100 text-slate-600',
  greyRed: 'bg-slate-100 text-loss',
};

/** 🟢 Early Setup green, 🟡 Developing amber, 🔵 Breakout Confirmed blue, 🟠 Extended orange, 🔴 Weak / Invalidated grey. */
export function signalTone(signal: string | null | undefined): Tone {
  if (!signal) return 'grey';
  if (signal.includes('Early Setup')) return 'green';
  if (signal.includes('Developing')) return 'amber';
  if (signal.includes('Breakout Confirmed')) return 'blue';
  if (signal.includes('Extended')) return 'orange';
  return 'grey'; // Weak / Invalidated, or anything the backend adds later
}

/** The badge already has a colour, so drop the leading emoji: "🟢 Early Setup" → "Early Setup". */
export function signalLabel(signal: string | null | undefined): string {
  if (!signal) return '—';
  return signal.replace(/^[^\p{L}]+/u, '') || signal;
}

/** Green for gains, red for losses, grey for zero or unknown. */
export function pnlClass(v: number | null | undefined): string {
  if (v === null || v === undefined || v === 0) return 'text-ink-muted';
  return v > 0 ? 'text-brand-dark' : 'text-loss';
}
