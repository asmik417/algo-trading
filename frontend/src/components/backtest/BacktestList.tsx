// Past backtests with status and live progress. Finished ones can be ticked (two at most) for Compare.
import clsx from 'clsx';
import { GitCompare, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { errorMessage } from '../../api/client';
import { isBacktestActive, useDeleteBacktest } from '../../hooks/useBacktests';
import { BACKTEST_PHASES, settingsLine } from '../../lib/backtest';
import { pnlClass } from '../../lib/colors';
import { formatDate, formatINR, formatNumber, formatPct } from '../../lib/format';
import type { Backtest } from '../../types/api';
import { RunProgress } from '../stocks/RunProgress';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { Card } from '../ui/Card';
import { Dialog } from '../ui/Dialog';
import { EmptyState } from '../ui/EmptyState';
import { useToast } from '../ui/Toast';

export function StatusBadge({ backtest }: { backtest: Backtest }) {
  if (backtest.status === 'done') return <Badge tone="green">Done</Badge>;
  if (backtest.status === 'failed') return <Badge tone="red">Failed</Badge>;
  return <Badge tone="amber">{backtest.status === 'queued' ? 'Queued' : 'Running'}</Badge>;
}

export function BacktestList({
  backtests,
  selected,
  onToggle,
  onCompare,
}: {
  backtests: Backtest[];
  selected: number[];
  onToggle: (id: number) => void;
  onCompare: () => void;
}) {
  const toast = useToast();
  const remove = useDeleteBacktest();
  const [toDelete, setToDelete] = useState<Backtest | null>(null);

  const confirmDelete = async () => {
    if (!toDelete) return;
    try {
      await remove.mutateAsync(toDelete.id);
      toast.success(`Deleted backtest #${toDelete.id}`);
    } catch (e) {
      toast.error(errorMessage(e));
    }
    setToDelete(null);
  };

  return (
    <Card
      title="Past backtests"
      right={
        <Button size="sm" variant="secondary" disabled={selected.length !== 2} onClick={onCompare}>
          <GitCompare className="h-4 w-4" aria-hidden /> Compare{' '}
          {selected.length ? `(${selected.length}/2)` : ''}
        </Button>
      }
    >
      {backtests.length === 0 ? (
        <EmptyState
          title="No backtests yet"
          description="Run one with the form to see how a strategy would have done."
        />
      ) : (
        <ul className="-my-2 divide-y divide-line" aria-label="Backtests">
          {backtests.map((b) => {
            const active = isBacktestActive(b);
            const ticked = selected.includes(b.id);
            const s = b.summary;
            return (
              <li key={b.id} className="py-3">
                <div className="flex items-start gap-3">
                  <input
                    type="checkbox"
                    aria-label={`Compare backtest #${b.id}`}
                    checked={ticked}
                    disabled={b.status !== 'done' || (!ticked && selected.length >= 2)}
                    onChange={() => onToggle(b.id)}
                    className="mt-1 h-4 w-4 accent-brand disabled:opacity-40"
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <Link
                        to={`/backtest/${b.id}`}
                        className="text-sm font-semibold text-ink hover:underline"
                      >
                        #{b.id} · {b.profile_name}
                      </Link>
                      <StatusBadge backtest={b} />
                    </div>
                    <p className="num mt-0.5 text-xs text-ink-muted">
                      {formatDate(b.start_date)} – {formatDate(b.end_date)} · {settingsLine(b)}
                    </p>
                    {s && (
                      <p className="num mt-1 text-sm text-ink">
                        {formatNumber(s.trades)} trades · win rate{' '}
                        {formatPct(s.win_rate_pct, { signed: false })} ·{' '}
                        <span className={pnlClass(s.total_pnl)}>
                          {formatINR(s.total_pnl, { signed: true, digits: 0 })}
                        </span>
                      </p>
                    )}
                    {b.status === 'failed' && (
                      <p className="mt-1 text-sm text-loss">{b.error ?? 'Failed'}</p>
                    )}
                    {active && (
                      <RunProgress
                        run={b}
                        label={`Backtest #${b.id} progress`}
                        phaseLabels={BACKTEST_PHASES}
                        formatCurrent={(d) => `scan date ${formatDate(d)}`}
                        unit="scan dates"
                      />
                    )}
                  </div>
                  <div className="flex shrink-0 items-center gap-1">
                    <Link
                      to={`/backtest/${b.id}`}
                      className={clsx(
                        'rounded-lg px-3 py-1.5 text-xs font-medium hover:bg-slate-50',
                        b.status === 'done' ? 'text-brand-dark' : 'text-ink-muted',
                      )}
                    >
                      {b.status === 'done' ? 'Results' : 'Open'}
                    </Link>
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={active}
                      onClick={() => setToDelete(b)}
                      aria-label={`Delete backtest #${b.id}`}
                    >
                      <Trash2 className="h-4 w-4" aria-hidden />
                    </Button>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}
      <Dialog
        open={toDelete !== null}
        onClose={() => setToDelete(null)}
        title="Delete backtest?"
        maxWidth="max-w-md"
      >
        {toDelete && (
          <div className="space-y-4 px-5 pb-5 pt-4">
            <p className="text-sm text-ink">
              Delete backtest <strong>#{toDelete.id}</strong> ({toDelete.profile_name},{' '}
              {formatDate(toDelete.start_date)} – {formatDate(toDelete.end_date)}) and its trades?
              This cannot be undone.
            </p>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setToDelete(null)}>
                Cancel
              </Button>
              <Button
                variant="danger"
                loading={remove.isPending}
                onClick={() => void confirmDelete()}
              >
                Delete
              </Button>
            </div>
          </div>
        )}
      </Dialog>
    </Card>
  );
}
