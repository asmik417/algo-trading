// Close price with EMA20 / EMA50 on top and volume bars underneath; optional target / stop / entry guide lines.
import { useMemo } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { DASH, formatCompact, formatDate, formatINR } from '../../lib/format';
import type { ChartData } from '../../types/api';
import { EmptyState } from '../ui/EmptyState';

const COLORS = {
  close: '#1f2937',
  ema20: '#00b386',
  ema50: '#f59e0b',
  volume: '#cbd5e1',
  target: '#00b386',
  stop: '#eb5b3c',
  entry: '#6366f1',
};
const Y_WIDTH = 58;

interface Props {
  chart: ChartData;
  target?: number | null;
  stopLoss?: number | null;
  entry?: number | null;
}

const isNum = (v: number | null | undefined): v is number =>
  typeof v === 'number' && Number.isFinite(v);

export function PriceChart({ chart, target, stopLoss, entry }: Props) {
  const data = useMemo(
    () =>
      chart.dates.map((date, i) => ({
        date,
        close: chart.close[i],
        ema20: chart.ema20[i],
        ema50: chart.ema50[i],
        volume: chart.volume[i],
      })),
    [chart],
  );

  const domain = useMemo<[number, number]>(() => {
    const values = [...chart.close, target, stopLoss].filter(isNum);
    const lo = Math.min(...values);
    const hi = Math.max(...values);
    const pad = (hi - lo) * 0.06 || 1;
    return [Math.floor(lo - pad), Math.ceil(hi + pad)];
  }, [chart.close, target, stopLoss]);

  if (data.length === 0) return <EmptyState title="Price history unavailable" />;

  const money = (v: unknown): string => (typeof v === 'number' ? formatINR(v) : DASH);

  return (
    <div>
      <ul className="mb-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-muted">
        <LegendItem color={COLORS.close} label="Close" />
        <LegendItem color={COLORS.ema20} label="EMA 20" />
        <LegendItem color={COLORS.ema50} label="EMA 50" />
        {isNum(target) && (
          <LegendItem color={COLORS.target} label={`Target ${formatINR(target)}`} dashed />
        )}
        {isNum(stopLoss) && (
          <LegendItem color={COLORS.stop} label={`Stop ${formatINR(stopLoss)}`} dashed />
        )}
        {isNum(entry) && (
          <LegendItem color={COLORS.entry} label={`Entry ${formatINR(entry)}`} dashed />
        )}
      </ul>
      <div role="img" aria-label="Price chart with 20 and 50 day moving averages and volume">
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={data} syncId="price" margin={{ top: 6, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="#eef0f3" vertical={false} />
            <XAxis dataKey="date" hide />
            <YAxis
              domain={domain}
              width={Y_WIDTH}
              tick={{ fontSize: 11, fill: '#6b7280' }}
              tickFormatter={(v: number) => formatINR(v, { digits: 0 })}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              labelFormatter={(label) => formatDate(String(label))}
              formatter={(value, name) => [money(value), String(name)]}
              contentStyle={{ borderRadius: 8, borderColor: '#e5e7eb', fontSize: 12 }}
            />
            {isNum(target) && (
              <ReferenceLine y={target} stroke={COLORS.target} strokeDasharray="5 4" />
            )}
            {isNum(stopLoss) && (
              <ReferenceLine y={stopLoss} stroke={COLORS.stop} strokeDasharray="5 4" />
            )}
            {isNum(entry) && (
              <ReferenceLine y={entry} stroke={COLORS.entry} strokeDasharray="5 4" />
            )}
            <Line
              type="monotone"
              dataKey="close"
              name="Close"
              stroke={COLORS.close}
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="ema20"
              name="EMA 20"
              stroke={COLORS.ema20}
              strokeWidth={1.5}
              dot={false}
              connectNulls
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="ema50"
              name="EMA 50"
              stroke={COLORS.ema50}
              strokeWidth={1.5}
              dot={false}
              connectNulls
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
        <ResponsiveContainer width="100%" height={84}>
          <BarChart data={data} syncId="price" margin={{ top: 0, right: 8, left: 0, bottom: 0 }}>
            <XAxis
              dataKey="date"
              tickFormatter={(d: string) => formatDate(d).slice(0, 6)}
              tick={{ fontSize: 11, fill: '#6b7280' }}
              minTickGap={36}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              width={Y_WIDTH}
              tick={{ fontSize: 11, fill: '#6b7280' }}
              tickFormatter={(v: number) => formatCompact(v)}
              axisLine={false}
              tickLine={false}
              tickCount={3}
            />
            <Tooltip
              labelFormatter={(label) => formatDate(String(label))}
              formatter={(value) => [
                typeof value === 'number' ? formatCompact(value) : DASH,
                'Volume',
              ]}
              contentStyle={{ borderRadius: 8, borderColor: '#e5e7eb', fontSize: 12 }}
            />
            <Bar dataKey="volume" name="Volume" fill={COLORS.volume} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function LegendItem({
  color,
  label,
  dashed = false,
}: {
  color: string;
  label: string;
  dashed?: boolean;
}) {
  return (
    <li className="flex items-center gap-1.5">
      <span
        className="inline-block w-4 border-t-2"
        style={{ borderColor: color, borderStyle: dashed ? 'dashed' : 'solid' }}
        aria-hidden
      />
      {label}
    </li>
  );
}
