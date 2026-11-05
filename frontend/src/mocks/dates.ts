// Date and randomness helpers for the mock layer. Everything is deterministic so fixtures look the same on every load.
import {
  addDays,
  differenceInCalendarDays,
  eachDayOfInterval,
  format,
  isWeekend,
  parseISO,
} from 'date-fns';

/** The latest trading day in the mock world (the day before "today", 05 Nov 2026). */
export const TRADING_DAY = '2026-11-04';
export const NOW_ISO = '2026-11-05T09:00:00Z';

export const toIso = (d: Date): string => format(d, 'yyyy-MM-dd');
export const shiftDays = (iso: string, n: number): string => toIso(addDays(parseISO(iso), n));
export const daysBetween = (fromIso: string, toIsoDate: string): number =>
  differenceInCalendarDays(parseISO(toIsoDate), parseISO(fromIso));

/** Weekdays from start to end, inclusive (holidays are ignored in mocks). */
export function weekdaysBetween(startIso: string, endIso: string): string[] {
  if (daysBetween(startIso, endIso) < 0) return [];
  return eachDayOfInterval({ start: parseISO(startIso), end: parseISO(endIso) })
    .filter((d) => !isWeekend(d))
    .map(toIso);
}

/** Small seeded random generator (mulberry32) keyed by a string. */
export function seeded(seed: string): () => number {
  let h = 1779033703 ^ seed.length;
  for (let i = 0; i < seed.length; i++) {
    h = Math.imul(h ^ seed.charCodeAt(i), 3432918353);
    h = (h << 13) | (h >>> 19);
  }
  let a = h >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export const round = (v: number, digits = 1): number => {
  const f = 10 ** digits;
  return Math.round(v * f) / f;
};
