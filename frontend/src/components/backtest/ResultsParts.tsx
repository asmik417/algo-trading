// Results page building blocks: stat tiles, caveats banner, equity curve, breakdown tables, loss-pattern bars.
import { format, parseISO } from 'date-fns';
import { AlertTriangle } from 'lucide-react';
import { useState } from 'react';
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
import { pnlClass } from '../../lib/colors';
import { DASH, formatDate, formatINR, formatNumber, formatPct } from '../../lib/format';
import type {
  BacktestBreakdownRow,
  BacktestLossPattern,
  BacktestResults,
  BacktestSummary,
  EquityPoint,
} from '../../types/api';
import { SignalBadge } from '../stocks/SignalBadge';
import { Card } from '../ui/Card';
import { EmptyState } from '../ui/EmptyState';
import { Stat } from '../ui/Stat';
import { Table, TableWrap, Td, Th } from '../ui/Table';
import { Tabs } from '../ui/Tabs';

export function StatTiles({ s }: { s: BacktestSummary }) {
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <Stat
        label="Trades"
        value={formatNumber(s.trades)}
        sub={`${formatNumber(s.closed)} closed · ${formatNumber(s.open_at_end)} open at end · skipped ${formatNumber(s.skipped_repeat)} repeat, ${formatNumber(s.skipped_no_fill)} no fill`}
      />
      <Stat
        label="Win rate"
        value={formatPct(s.win_rate_pct, { signed: false })}
        sub={`${formatNumber(s.wins)} won · ${formatNumber(s.losses)} lost (closed trades)`}
      />
      <Stat
        label="Avg win / Avg loss"
        value={
          <>
            <span className={pnlClass(s.avg_win_pct)}>{formatPct(s.avg_win_pct)}</span>
            <span className="mx-1.5 text-ink-faint">/</span>
            <span className={pnlClass(s.avg_loss_pct)}>{formatPct(s.avg_loss_pct)}</span>
          </>
        }
        sub={`Avg days held ${formatNumber(s.avg_days_held, 1)}`}
      />
      <Stat
        label="Expectancy"
        value={s.expectancy_r === null ? DASH : `${formatNumber(s.expectancy_r, 2)} R`}
        valueClassName={pnlClass(s.expectancy_r)}
        sub="Mean R-multiple per closed trade"
      />
      <Stat
        label="Profit factor"
        value={formatNumber(s.profit_factor, 2)}
        sub="Gross wins ÷ gross losses"
      />
      <Stat
        label="Total P&L"
        value={formatINR(s.total_pnl, { signed: true, digits: 0 })}
        valueClassName={pnlClass(s.total_pnl)}
        sub={`${s.exits.target_hit} target · ${s.exits.stop_hit} stop · ${s.exits.horizon_closed} horizon · ${s.exits.open} open`}
      />
      <Stat
        label="Max drawdown"
        value={formatPct(s.max_drawdown_pct, { signed: false })}
        valueClassName={s.max_drawdown_pct ? 'text-loss' : undefined}
        sub="Of capital per trade × 10"
      />
      <Stat
        label="vs Nifty"
        value={
          <>
            <span className={pnlClass(s.avg_pnl_pct)}>{formatPct(s.avg_pnl_pct)}</span>
            <span className="mx-1.5 text-sm font-normal text-ink-faint">vs</span>
            <span className={pnlClass(s.nifty_avg_pct)}>{formatPct(s.nifty_avg_pct)}</span>
          </>
        }
        sub="Average closed trade vs Nifty 50 over the same days"
      />
    </div>
  );
}

export function CaveatsBanner({ caveats }: { caveats: string[] }) {
  if (caveats.length === 0) return null;
  return (
    <section aria-label="Caveats" className="rounded-lg border border-amber-200 bg-amber-50 p-4">
      <h3 className="flex items-center gap-2 text-sm font-semibold text-amber-900">
        <AlertTriangle className="h-4 w-4" aria-hidden /> Read before trusting these numbers
      </h3>
      <ul className="mt-2 list-disc space-y-1 pl-6 text-sm text-amber-900">
        {caveats.map((c) => (
          <li key={c}>{c}</li>
        ))}
      </ul>
    </section>
  );
}

export function EquityChart({
  points,
  maxDrawdownPct,
}: {
  points: EquityPoint[];
  maxDrawdownPct: number | null;
}) {
  if (points.length === 0)
    return (
      <EmptyState
        title="No closed trades yet"
        description="The equity curve uses closed trades only."
      />
    );
  const money = (v: unknown) =>
    typeof v === 'number' ? formatINR(v, { signed: true, digits: 0 }) : DASH;
  return (
    <Card
      title="Equity curve"
      right={
        <span className="num text-xs text-ink-muted">
          Closed trades, cumulative P&amp;L · max drawdown{' '}
          {formatPct(maxDrawdownPct, { signed: false })}
        </span>
      }
    >
      <div role="img" aria-label="Cumulative profit and loss of closed trades by exit date">
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={points} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="#eef0f3" vertical={false} />
            <XAxis
              dataKey="date"
              tickFormatter={(d: string) => format(parseISO(d), 'dd MMM yy')}
              tick={{ fontSize: 11, fill: '#6b7280' }}
              minTickGap={40}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              width={72}
              tick={{ fontSize: 11, fill: '#6b7280' }}
              tickFormatter={(v: number) => formatINR(v, { digits: 0 })}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              labelFormatter={(d) => formatDate(String(d))}
              formatter={(v) => [money(v), 'Cumulative P&L']}
              contentStyle={{ borderRadius: 8, borderColor: '#e5e7eb', fontSize: 12 }}
            />
            <ReferenceLine y={0} stroke="#94a3b8" strokeDasharray="3 3" />
            <Line
              type="monotone"
              dataKey="pnl"
              stroke="#00b386"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}

type GroupKey = 'by_signal' | 'by_stage' | 'by_market_cap' | 'by_sector' | 'by_month';
const GROUPS: { key: GroupKey; label: string; column: string }[] = [
  { key: 'by_signal', label: 'Signal', column: 'Signal' },
  { key: 'by_stage', label: 'Stage', column: 'Stage' },
  { key: 'by_market_cap', label: 'Market cap', column: 'Market cap' },
  { key: 'by_sector', label: 'Sector', column: 'Sector' },
  { key: 'by_month', label: 'Month', column: 'Entry month' },
];

const groupName = (key: GroupKey, row: BacktestBreakdownRow) =>
  key === 'by_signal' ? (
    <SignalBadge signal={row.key} />
  ) : key === 'by_month' && /^\d{4}-\d{2}$/.test(row.key) ? (
    format(parseISO(`${row.key}-01`), 'MMM yyyy')
  ) : (
    row.key
  );

export function BreakdownTables({ results }: { results: BacktestResults }) {
  const [tab, setTab] = useState<GroupKey>('by_signal');
  const rows = results[tab];
  const column = GROUPS.find((g) => g.key === tab)?.column ?? '';
  return (
    <Card title="Breakdowns">
      <Tabs
        tabs={GROUPS.map((g) => ({ key: g.key, label: g.label, count: results[g.key].length }))}
        value={tab}
        onChange={setTab}
        label="Breakdown by"
      />
      <TableWrap maxHeight="max-h-[24rem]" className="mt-3">
        <Table>
          <thead>
            <tr>
              <Th>{column}</Th>
              <Th align="right">Trades</Th>
              <Th align="right">Win rate</Th>
              <Th align="right">Avg P&amp;L</Th>
              <Th align="right">Total P&amp;L</Th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.key}>
                <Td>{groupName(tab, r)}</Td>
                <Td align="right">{formatNumber(r.trades)}</Td>
                <Td align="right">{formatPct(r.win_rate_pct, { signed: false })}</Td>
                <Td align="right" className={pnlClass(r.avg_pnl_pct)}>
                  {formatPct(r.avg_pnl_pct)}
                </Td>
                <Td align="right" className={pnlClass(r.total_pnl)}>
                  {formatINR(r.total_pnl, { signed: true, digits: 0 })}
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
      </TableWrap>
    </Card>
  );
}

/** Uses the Loss Analysis labels (GET /reviews/tags) when the key is known there, else the backend's label. */
export function LossPatternList({
  patterns,
  labels,
  losses,
}: {
  patterns: BacktestLossPattern[];
  labels: Map<string, string>;
  losses: number;
}) {
  const max = Math.max(1, ...patterns.map((p) => p.count));
  return (
    <Card
      title="What went wrong on losing trades"
      right={
        <span className="num text-xs text-ink-muted">
          {formatNumber(losses)} losing trades; a trade can match several patterns
        </span>
      }
    >
      {patterns.length === 0 ? (
        <p className="text-sm text-ink-muted">No losing trades to tag.</p>
      ) : (
        <ul className="space-y-2">
          {patterns.map((p) => (
            <li key={p.key} className="flex items-center gap-3 text-sm">
              <span
                className="w-56 shrink-0 truncate text-ink"
                title={labels.get(p.key) ?? p.label}
              >
                {labels.get(p.key) ?? p.label}
              </span>
              <div
                className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100"
                role="img"
                aria-label={`${labels.get(p.key) ?? p.label}: ${p.count}`}
              >
                <div
                  className="h-full rounded-full bg-loss/80"
                  style={{ width: `${(p.count / max) * 100}%` }}
                />
              </div>
              <span className="num w-10 text-right font-medium text-ink">{p.count}</span>
              <span className="num w-14 text-right text-xs text-ink-muted">
                {formatPct(p.share_pct, { signed: false, digits: 0 })}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
