// Builds a believable 130-day price chart (close, EMA20, EMA50, volume) for any symbol.
import type { ChartData } from '../types/api';
import { TRADING_DAY, round, seeded, shiftDays, weekdaysBetween } from './dates';

function ema(values: number[], period: number): (number | null)[] {
  const k = 2 / (period + 1);
  const out: (number | null)[] = [];
  let prev: number | null = null;
  values.forEach((v, i) => {
    if (i < period - 1) {
      out.push(null);
      return;
    }
    prev =
      prev === null
        ? values.slice(0, period).reduce((a, b) => a + b, 0) / period
        : v * k + prev * (1 - k);
    out.push(round(prev, 2));
  });
  return out;
}

/** `price` is the last close; `trend3mPct` shapes the walk so the chart agrees with the 3-month change. */
export function buildChart(
  symbol: string,
  price: number,
  trend3mPct: number,
  days = 130,
): ChartData {
  const rand = seeded(`chart:${symbol}`);
  const dates = weekdaysBetween(shiftDays(TRADING_DAY, -Math.ceil(days * 1.5)), TRADING_DAY).slice(
    -days,
  );
  const driftPerDay = Math.log(1 + trend3mPct / 100) / 63;
  const raw: number[] = [];
  let level = 100;
  dates.forEach(() => {
    level *= Math.exp(driftPerDay * 0.6 + (rand() - 0.5) * 0.03);
    raw.push(level);
  });
  const scale = price / raw[raw.length - 1];
  const close = raw.map((v) => round(v * scale, 2));
  const baseVolume = 50_000 + Math.floor(rand() * 400_000);
  const volume = close.map(() => Math.round(baseVolume * (0.6 + rand() * 0.9)));
  return { dates, close, ema20: ema(close, 20), ema50: ema(close, 50), volume };
}
