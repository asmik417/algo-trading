// One-line technical read-out: RSI, MACD, trend, ATR and the three EMAs.
import { DASH, formatINR, formatMultiple, formatNumber } from '../../lib/format';
import type { Indicators } from '../../types/api';

/** BULLISH → Bullish, STRONG_UPTREND → Strong uptrend. */
const words = (v: string | null): string =>
  v ? v.charAt(0) + v.slice(1).toLowerCase().replace(/_/g, ' ') : DASH;

export function IndicatorsStrip({ data }: { data: Indicators }) {
  const items: [string, string][] = [
    ['RSI', formatNumber(data.rsi, 0)],
    ['MACD', words(data.macd_signal)],
    ['Trend', words(data.ema_trend)],
    ['ATR', formatINR(data.atr)],
    ['EMA 20', formatINR(data.ema20)],
    ['EMA 50', formatINR(data.ema50)],
    ['EMA 200', formatINR(data.ema200)],
    ['Bollinger', data.bb_position ?? DASH],
    ['Volume vs avg', formatMultiple(data.volume_ratio)],
  ];
  return (
    <dl className="flex flex-wrap gap-x-6 gap-y-2 rounded-lg border border-line px-4 py-3 text-sm">
      {items.map(([label, value]) => (
        <div key={label}>
          <dt className="text-xs text-ink-muted">{label}</dt>
          <dd className="num font-medium text-ink">{value}</dd>
        </div>
      ))}
    </dl>
  );
}
