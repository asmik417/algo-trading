// Every audit event on a position (open, extend, shorten, due, close, note), newest first, with its reason text.
import clsx from 'clsx';
import { ArrowRight } from 'lucide-react';
import { formatDate, formatINR } from '../../lib/format';
import { EVENT_LABEL } from '../../lib/labels';
import type { EventType, PositionEvent } from '../../types/api';

const DOT: Record<EventType, string> = {
  open: 'bg-brand',
  extend: 'bg-amber-500',
  shorten: 'bg-blue-500',
  due: 'bg-amber-500',
  close: 'bg-slate-700',
  note: 'bg-slate-400',
};

export function EventsTimeline({ events }: { events: PositionEvent[] }) {
  const ordered = [...events].sort(
    (a, b) => b.event_date.localeCompare(a.event_date) || b.id - a.id,
  );
  return (
    <ol className="space-y-4">
      {ordered.map((e) => (
        <li key={e.id} className="relative pl-6">
          <span
            className={clsx('absolute left-0 top-1.5 h-2.5 w-2.5 rounded-full', DOT[e.event_type])}
            aria-hidden
          />
          <div className="flex flex-wrap items-baseline gap-x-2 text-sm">
            <span className="font-medium text-ink">{EVENT_LABEL[e.event_type]}</span>
            <span className="text-xs text-ink-muted">{formatDate(e.event_date)}</span>
            {e.price !== null && (
              <span className="num text-xs text-ink-muted">at {formatINR(e.price)}</span>
            )}
          </div>
          {(e.event_type === 'extend' || e.event_type === 'shorten') &&
            e.old_exit_date &&
            e.new_exit_date && (
              <div className="num mt-0.5 flex items-center gap-1.5 text-xs text-ink-muted">
                Exit date {formatDate(e.old_exit_date)}{' '}
                <ArrowRight className="h-3 w-3" aria-hidden /> {formatDate(e.new_exit_date)}
              </div>
            )}
          {e.reason && <p className="mt-1 text-sm text-ink">{e.reason}</p>}
        </li>
      ))}
    </ol>
  );
}
