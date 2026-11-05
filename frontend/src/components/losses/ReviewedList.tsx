// Finished reviews as expandable cards; Edit reopens the form.
import clsx from 'clsx';
import { ChevronDown, ClipboardList } from 'lucide-react';
import { useState } from 'react';
import { formatDate, formatINR, formatPct } from '../../lib/format';
import { CLOSE_REASON_LABEL } from '../../lib/labels';
import type { Review, ReviewTag } from '../../types/api';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { EmptyState } from '../ui/EmptyState';

function Block({ title, text }: { title: string; text: string }) {
  return (
    <div>
      <h4 className="text-xs font-semibold uppercase tracking-wide text-ink-muted">{title}</h4>
      <p className="mt-0.5 whitespace-pre-wrap text-sm text-ink">{text.trim() ? text : '—'}</p>
    </div>
  );
}

function ReviewCard({
  review,
  tags,
  onEdit,
}: {
  review: Review;
  tags: Map<string, string>;
  onEdit: (r: Review) => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <li className="rounded-lg border border-line bg-white">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-start gap-3 rounded-lg p-4 text-left hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand/40"
      >
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span className="text-base font-semibold text-ink">{review.symbol}</span>
            <span className="num text-sm font-semibold text-loss">
              {formatINR(review.pnl, { signed: true })} ({formatPct(review.pnl_pct)})
            </span>
            <span className="text-xs text-ink-muted">
              {CLOSE_REASON_LABEL[review.close_reason]} · closed {formatDate(review.closed_on)}
            </span>
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {review.reasons.map((key) => (
              <Badge key={key}>{tags.get(key) ?? key}</Badge>
            ))}
          </div>
        </div>
        <ChevronDown
          className={clsx('mt-1 h-4 w-4 shrink-0 text-ink-muted transition', open && 'rotate-180')}
          aria-hidden
        />
      </button>
      {open && (
        <div className="space-y-3 border-t border-line p-4">
          <Block title="Mistakes" text={review.mistakes} />
          <Block title="Lesson" text={review.lesson} />
          <Block title="What should change" text={review.algo_change} />
          <div className="flex items-center justify-between pt-1">
            <span className="text-xs text-ink-muted">
              Reviewed {formatDate(review.reviewed_on)}
            </span>
            <Button size="sm" variant="secondary" onClick={() => onEdit(review)}>
              Edit
            </Button>
          </div>
        </div>
      )}
    </li>
  );
}

export function ReviewedList({
  reviews,
  tags,
  onEdit,
}: {
  reviews: Review[];
  tags: ReviewTag[];
  onEdit: (r: Review) => void;
}) {
  const labels = new Map(tags.map((t) => [t.key, t.label]));
  return (
    <section aria-label="Reviewed losses">
      <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink">
        Reviewed
        <span className="num rounded-full bg-slate-100 px-2 text-xs font-medium text-ink-muted">
          {reviews.length}
        </span>
      </h2>
      {reviews.length === 0 ? (
        <EmptyState
          icon={ClipboardList}
          title="No reviews yet"
          description="Reviews you write appear here with their lessons."
        />
      ) : (
        <ul className="space-y-3">
          {reviews.map((r) => (
            <ReviewCard key={r.id} review={r} tags={labels} onEdit={onEdit} />
          ))}
        </ul>
      )}
    </section>
  );
}
