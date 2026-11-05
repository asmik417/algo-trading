// Position value over time (daily marks) with lines for target value, stop value, amount invested, and the exit dates.
import { format } from 'date-fns';
import { useMemo } from 'react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { DASH, formatDate, formatINR } from '../../lib/format';
import type { PositionDetail } from '../../types/api';
import { EmptyState } from '../ui/EmptyState';

const ts = (iso: string): number => new Date(`${iso}T00:00:00`).getTime();
const DAY_MS = 86_400_000;

/** At least three days wide, so a position opened today still gets a readable axis. */
function xDomainOf(xs: number[]): [number, number] {
  const lo = Math.min(...xs);
  return [lo, Math.max(...xs, lo + 3 * DAY_MS)];
}

/** Up to six whole-day ticks. Explicit ticks avoid Recharts producing the same day twice on a short axis. */
function dayTicks([lo, hi]: [number, number]): number[] {
  const days = Math.round((hi - lo) / DAY_MS);
  const count = Math.min(6, days + 1);
  const ticks = Array.from(
    { length: count },
    (_, i) => lo + Math.round((i * days) / Math.max(1, count - 1)) * DAY_MS,
  );
  return [...new Set(ticks)];
}
const COLORS = {
  value: '#1f2937',
  target: '#00b386',
  stop: '#eb5b3c',
  invested: '#94a3b8',
  original: '#64748b',
  planned: '#f59e0b',
};

export function MarksChart({ position }: { position: PositionDetail }) {
  const { data, xDomain, yDomain, targetValue, stopValue } = useMemo(() => {
    const points = [
      { t: ts(position.opened_on), value: position.invested },
      ...position.marks.map((m) => ({ t: ts(m.mark_date), value: m.value })),
    ];
    const targetValue = position.target === null ? null : position.target * position.qty;
    const stopValue = position.stop_loss === null ? null : position.stop_loss * position.qty;
    const ys = [...points.map((p) => p.value), position.invested, targetValue, stopValue].filter(
      (v): v is number => v !== null,
    );
    const lo = Math.min(...ys);
    const hi = Math.max(...ys);
    const pad = (hi - lo) * 0.08 || 100;
    const xs = [
      points[0].t,
      points[points.length - 1].t,
      ts(position.original_exit_date),
      ts(position.planned_exit_date),
    ];
    return {
      data: points,
      xDomain: xDomainOf(xs),
      yDomain: [Math.floor(lo - pad), Math.ceil(hi + pad)] as [number, number],
      targetValue,
      stopValue,
    };
  }, [position]);

  if (position.marks.length === 0)
    return (
      <EmptyState
        title="No daily marks yet"
        description="The first mark appears after the next daily update."
      />
    );

  const extended = position.original_exit_date !== position.planned_exit_date;
  const label = (
    value: string,
    fill: string,
    where: 'insideTopRight' | 'insideBottomLeft' = 'insideTopRight',
  ) => ({ value, position: where, fontSize: 11, fill });

  return (
    <div role="img" aria-label="Position value over time with target and stop levels">
      <ResponsiveContainer width="100%" height={230}>
        <LineChart data={data} margin={{ top: 14, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="#eef0f3" vertical={false} />
          <XAxis
            dataKey="t"
            type="number"
            scale="time"
            domain={xDomain}
            ticks={dayTicks(xDomain)}
            tickFormatter={(v: number) => format(v, 'dd MMM')}
            tick={{ fontSize: 11, fill: '#6b7280' }}
            axisLine={false}
            tickLine={false}
            minTickGap={28}
          />
          <YAxis
            domain={yDomain}
            width={64}
            tick={{ fontSize: 11, fill: '#6b7280' }}
            tickFormatter={(v: number) => formatINR(v, { digits: 0 })}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            labelFormatter={(v) =>
              typeof v === 'number' ? formatDate(format(v, 'yyyy-MM-dd')) : DASH
            }
            formatter={(value) => [typeof value === 'number' ? formatINR(value) : DASH, 'Value']}
            contentStyle={{ borderRadius: 8, borderColor: '#e5e7eb', fontSize: 12 }}
          />
          {targetValue !== null && (
            <ReferenceLine
              y={targetValue}
              stroke={COLORS.target}
              strokeDasharray="5 4"
              label={label('Target', COLORS.target, 'insideBottomLeft')}
            />
          )}
          {stopValue !== null && (
            <ReferenceLine
              y={stopValue}
              stroke={COLORS.stop}
              strokeDasharray="5 4"
              label={label('Stop', COLORS.stop, 'insideBottomLeft')}
            />
          )}
          <ReferenceLine y={position.invested} stroke={COLORS.invested} strokeDasharray="2 4" />
          <ReferenceLine
            x={ts(position.original_exit_date)}
            stroke={COLORS.original}
            strokeDasharray="4 3"
            label={label('Original exit', COLORS.original)}
          />
          {extended && (
            <ReferenceLine
              x={ts(position.planned_exit_date)}
              stroke={COLORS.planned}
              strokeDasharray="4 3"
              label={label('Planned exit', '#b45309')}
            />
          )}
          <Line
            type="monotone"
            dataKey="value"
            stroke={COLORS.value}
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
      <p className="mt-1 text-xs text-ink-muted">
        Dotted grey line = amount invested ({formatINR(position.invested)}).
      </p>
    </div>
  );
}
