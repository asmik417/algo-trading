// Display helpers: rupees, percentages and dates. Missing data is always shown as "—", never "null" or 0.
import { format, parseISO } from 'date-fns';

export const DASH = '—';

const inrNumber = new Intl.NumberFormat('en-IN', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});
const plainNumber = (digits: number) =>
  new Intl.NumberFormat('en-IN', { minimumFractionDigits: digits, maximumFractionDigits: digits });

const isMissing = (v: number | null | undefined): v is null | undefined =>
  v === null || v === undefined || !Number.isFinite(v);

/** ₹1,23,456.00 (Indian digit grouping). */
export function formatINR(
  v: number | null | undefined,
  opts: { signed?: boolean; digits?: number } = {},
): string {
  if (isMissing(v)) return DASH;
  const sign = v < 0 ? '-' : opts.signed && v > 0 ? '+' : '';
  return `${sign}₹${(opts.digits === undefined ? inrNumber : plainNumber(opts.digits)).format(Math.abs(v))}`;
}

/** +4.2 % / -1.2 %. Pass signed:false for values that are not changes (e.g. a win rate). */
export function formatPct(
  v: number | null | undefined,
  opts: { signed?: boolean; digits?: number } = {},
): string {
  if (isMissing(v)) return DASH;
  const { signed = true, digits = 1 } = opts;
  const sign = v < 0 ? '-' : signed && v > 0 ? '+' : '';
  return `${sign}${plainNumber(digits).format(Math.abs(v))} %`;
}

/** 1,23,456 or 12.5 — plain number with Indian grouping. */
export function formatNumber(v: number | null | undefined, digits = 0): string {
  if (isMissing(v)) return DASH;
  return plainNumber(digits).format(v);
}

/** 1.6× */
export function formatMultiple(v: number | null | undefined): string {
  if (isMissing(v)) return DASH;
  return `${plainNumber(1).format(v)}×`;
}

/** ISO date (or timestamp) → 05 Nov 2026. */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return DASH;
  const d = parseISO(iso);
  return Number.isNaN(d.getTime()) ? DASH : format(d, 'dd MMM yyyy');
}

/** ISO timestamp → 05 Nov 2026, 14:30 (viewer's local time). */
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return DASH;
  const d = parseISO(iso);
  return Number.isNaN(d.getTime()) ? DASH : format(d, 'dd MMM yyyy, HH:mm');
}

/** Rupees → crore: 340000000000 becomes ₹34,000 Cr. */
export function formatCrore(rupees: number | null | undefined): string {
  if (isMissing(rupees)) return DASH;
  const crore = rupees / 1e7;
  return `₹${plainNumber(Math.abs(crore) < 100 ? 1 : 0).format(crore)} Cr`;
}

/** 12,345 → 12K style, for chart axes. */
export function formatCompact(v: number): string {
  return new Intl.NumberFormat('en-IN', { notation: 'compact', maximumFractionDigits: 1 }).format(
    v,
  );
}
