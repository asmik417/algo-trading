// Right-side drawer for one position: P&L, key numbers, value chart, benchmark, event timeline and actions.
import { CalendarClock, CalendarMinus, NotebookPen, XCircle } from 'lucide-react';
import { Link } from 'react-router-dom';
import { usePositionDetail } from '../../hooks/usePositions';
import { pnlClass } from '../../lib/colors';
import { formatDate, formatINR, formatNumber, formatPct } from '../../lib/format';
import type { Position } from '../../types/api';
import { SignalBadge } from '../stocks/SignalBadge';
import { Button } from '../ui/Button';
import { Drawer } from '../ui/Drawer';
import { ErrorNotice } from '../ui/ErrorNotice';
import { Skeleton } from '../ui/Skeleton';
import { EventsTimeline } from './EventsTimeline';
import { MarksChart } from './MarksChart';
import { StatusBadge } from './StatusBadge';

export type DrawerAction = 'extend' | 'shorten' | 'close' | 'note';

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-ink-muted">{label}</dt>
      <dd className="num text-sm font-medium text-ink">{value}</dd>
    </div>
  );
}

export function PositionDrawer({
  positionId,
  onClose,
  onAction,
}: {
  positionId: number | null;
  onClose: () => void;
  onAction: (action: DrawerAction, position: Position) => void;
}) {
  const { data: p, error, refetch } = usePositionDetail(positionId);
  const live = p ? p.status !== 'closed' : false;

  return (
    <Drawer
      open={positionId !== null}
      onClose={onClose}
      title={p ? `${p.symbol} position` : 'Position details'}
    >
      {error ? (
        <div className="p-5 pt-14">
          <ErrorNotice error={error} onRetry={() => void refetch()} />
        </div>
      ) : !p ? (
        <div className="space-y-4 p-5 pt-14" aria-busy="true">
          <Skeleton className="h-8 w-1/2" />
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-56 w-full" />
        </div>
      ) : (
        <>
          <header className="border-b border-line px-5 pb-4 pr-14 pt-5">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-xl font-semibold text-ink">{p.symbol}</h2>
              <StatusBadge position={p} />
              {p.signal && <SignalBadge signal={p.signal} />}
            </div>
            <div className="mt-3 flex items-end gap-3">
              <span className={`num text-2xl font-semibold ${pnlClass(p.pnl)}`}>
                {formatINR(p.pnl, { signed: true })}
              </span>
              <span className={`num pb-0.5 text-sm font-medium ${pnlClass(p.pnl_pct)}`}>
                {formatPct(p.pnl_pct)}
              </span>
            </div>
            {p.stage && <p className="mt-1 text-xs text-ink-muted">Stage when opened: {p.stage}</p>}
          </header>

          <div className="space-y-6 px-5 py-5">
            <dl className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-4">
              <Fact label="Opened" value={formatDate(p.opened_on)} />
              <Fact label="Entry" value={formatINR(p.entry_price)} />
              <Fact label="Quantity" value={formatNumber(p.qty)} />
              <Fact label="Invested" value={formatINR(p.invested)} />
              <Fact label="Last close" value={formatINR(p.last_close)} />
              <Fact label="Value" value={formatINR(p.current_value)} />
              <Fact label="Target" value={formatINR(p.target)} />
              <Fact label="Stop-loss" value={formatINR(p.stop_loss)} />
              <Fact
                label={p.status === 'closed' ? 'Closed on' : 'Exit by'}
                value={formatDate(p.status === 'closed' ? p.closed_on : p.planned_exit_date)}
              />
              {p.status === 'closed' ? (
                <Fact label="Exit price" value={formatINR(p.exit_price)} />
              ) : (
                <Fact label="Days left" value={formatNumber(p.days_to_exit)} />
              )}
              <Fact label="Days held" value={formatNumber(p.days_held)} />
              {p.original_exit_date !== p.planned_exit_date && (
                <Fact label="Original exit" value={formatDate(p.original_exit_date)} />
              )}
            </dl>

            <section>
              <h3 className="mb-2 text-sm font-semibold text-ink">Value over time</h3>
              <MarksChart position={p} />
              {p.benchmark && (
                <p className="num mt-2 text-sm text-ink-muted">
                  {p.benchmark.symbol === 'NIFTY 50' ? 'Nifty 50' : p.benchmark.symbol} since open:{' '}
                  <strong className={pnlClass(p.benchmark.change_pct_since_open)}>
                    {formatPct(p.benchmark.change_pct_since_open)}
                  </strong>
                </p>
              )}
            </section>

            {p.needs_review && (
              <p className="rounded-lg bg-loss-soft px-3 py-2 text-sm text-loss">
                This loss has no review yet.{' '}
                <Link to="/losses" className="font-medium underline">
                  Review it in Loss Analysis
                </Link>
              </p>
            )}

            <section>
              <h3 className="mb-3 text-sm font-semibold text-ink">Timeline</h3>
              <EventsTimeline events={p.events} />
            </section>
          </div>

          <footer className="sticky bottom-0 mt-auto flex flex-wrap gap-2 border-t border-line bg-white px-5 py-3">
            {live && (
              <>
                <Button size="sm" onClick={() => onAction('extend', p)}>
                  <CalendarClock className="h-4 w-4" aria-hidden /> Extend
                </Button>
                <Button size="sm" variant="secondary" onClick={() => onAction('shorten', p)}>
                  <CalendarMinus className="h-4 w-4" aria-hidden /> Shorten
                </Button>
                <Button size="sm" variant="secondary" onClick={() => onAction('close', p)}>
                  <XCircle className="h-4 w-4" aria-hidden /> Close now
                </Button>
              </>
            )}
            <Button size="sm" variant="secondary" onClick={() => onAction('note', p)}>
              <NotebookPen className="h-4 w-4" aria-hidden /> Add note
            </Button>
          </footer>
        </>
      )}
    </Drawer>
  );
}
