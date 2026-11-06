// Two finished backtests side by side. The better value of each comparable metric is highlighted.
import clsx from 'clsx';
import { X } from 'lucide-react';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { pnlClass } from '../../lib/colors';
import { formatDate, formatINR, formatNumber, formatPct } from '../../lib/format';
import type { Backtest, BacktestSummary } from '../../types/api';
import { Button } from '../ui/Button';
import { Card } from '../ui/Card';
import { settingsLine } from '../../lib/backtest';

type Better = 'higher' | 'lower' | null;
interface Row {
  label: string;
  value: (s: BacktestSummary, b: Backtest) => number | null;
  show: (s: BacktestSummary, b: Backtest) => ReactNode;
  better: Better;
}

const ROWS: Row[] = [
  {
    label: 'Trades',
    value: (s) => s.trades,
    show: (s) =>
      `${formatNumber(s.trades)} (${formatNumber(s.closed)} closed, ${formatNumber(s.open_at_end)} open)`,
    better: null,
  },
  {
    label: 'Win rate',
    value: (s) => s.win_rate_pct,
    show: (s) => formatPct(s.win_rate_pct, { signed: false }),
    better: 'higher',
  },
  {
    label: 'Avg win',
    value: (s) => s.avg_win_pct,
    show: (s) => formatPct(s.avg_win_pct),
    better: 'higher',
  },
  {
    label: 'Avg loss',
    value: (s) => s.avg_loss_pct,
    show: (s) => formatPct(s.avg_loss_pct),
    better: 'higher',
  },
  {
    label: 'Expectancy',
    value: (s) => s.expectancy_r,
    show: (s) => (s.expectancy_r === null ? '—' : `${formatNumber(s.expectancy_r, 2)} R`),
    better: 'higher',
  },
  {
    label: 'Profit factor',
    value: (s) => s.profit_factor,
    show: (s) => formatNumber(s.profit_factor, 2),
    better: 'higher',
  },
  {
    label: 'Total P&L',
    value: (s) => s.total_pnl,
    show: (s) => (
      <span className={pnlClass(s.total_pnl)}>
        {formatINR(s.total_pnl, { signed: true, digits: 0 })}
      </span>
    ),
    better: 'higher',
  },
  {
    label: 'Max drawdown',
    value: (s) => s.max_drawdown_pct,
    show: (s) => formatPct(s.max_drawdown_pct, { signed: false }),
    better: 'lower',
  },
  {
    label: 'Avg trade vs Nifty',
    value: (s) =>
      s.avg_pnl_pct === null || s.nifty_avg_pct === null ? null : s.avg_pnl_pct - s.nifty_avg_pct,
    show: (s) => `${formatPct(s.avg_pnl_pct)} vs ${formatPct(s.nifty_avg_pct)}`,
    better: 'higher',
  },
  {
    label: 'Avg days held',
    value: (s) => s.avg_days_held,
    show: (s) => formatNumber(s.avg_days_held, 1),
    better: null,
  },
  {
    label: 'Exits',
    value: () => null,
    show: (s) =>
      `${s.exits.target_hit} target · ${s.exits.stop_hit} stop · ${s.exits.horizon_closed} horizon`,
    better: null,
  },
];

export function ComparePanel({ a, b, onClose }: { a: Backtest; b: Backtest; onClose: () => void }) {
  const pair = [a, b];
  return (
    <Card
      title="Compare"
      right={
        <Button size="sm" variant="ghost" onClick={onClose} aria-label="Close compare">
          <X className="h-4 w-4" aria-hidden />
        </Button>
      }
    >
      <div className="overflow-x-auto">
        <table className="w-full text-sm" aria-label="Backtest comparison">
          <thead>
            <tr className="text-left">
              <th className="w-40 pb-2 text-xs font-medium uppercase tracking-wide text-ink-muted" />
              {pair.map((x) => (
                <th key={x.id} className="pb-2 align-top font-normal">
                  <Link to={`/backtest/${x.id}`} className="font-semibold text-ink hover:underline">
                    #{x.id} · {x.profile_name}
                  </Link>
                  <div className="num text-xs text-ink-muted">
                    {formatDate(x.start_date)} – {formatDate(x.end_date)}
                  </div>
                  <div className="text-xs text-ink-muted">{settingsLine(x)}</div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ROWS.map((row) => {
              const vals = pair.map((x) => (x.summary ? row.value(x.summary, x) : null));
              const [va, vb] = vals;
              const winner =
                row.better && va !== null && vb !== null && va !== vb
                  ? (row.better === 'higher' ? va > vb : va < vb)
                    ? 0
                    : 1
                  : null;
              return (
                <tr key={row.label} className="border-t border-line/70">
                  <th
                    scope="row"
                    className="py-2 pr-3 text-left text-xs font-medium uppercase tracking-wide text-ink-muted"
                  >
                    {row.label}
                  </th>
                  {pair.map((x, i) => (
                    <td
                      key={x.id}
                      className={clsx(
                        'num py-2 pr-3',
                        winner === i && 'font-semibold text-brand-dark',
                      )}
                    >
                      {x.summary ? row.show(x.summary, x) : '—'}
                      {winner === i && <span className="sr-only"> (better)</span>}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
