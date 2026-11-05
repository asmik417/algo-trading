// Closed losing positions that still need a review.
import { CheckCircle2 } from 'lucide-react';
import { formatDate, formatINR, formatNumber, formatPct } from '../../lib/format';
import type { Position } from '../../types/api';
import { StatusBadge } from '../tracker/StatusBadge';
import { Button } from '../ui/Button';
import { Card } from '../ui/Card';
import { EmptyState } from '../ui/EmptyState';

export function PendingLossList({
  positions,
  onReview,
}: {
  positions: Position[];
  onReview: (p: Position) => void;
}) {
  return (
    <section aria-label="Losses waiting for review">
      <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink">
        Waiting for review
        <span className="num rounded-full bg-loss-soft px-2 text-xs font-medium text-loss">
          {positions.length}
        </span>
      </h2>
      {positions.length === 0 ? (
        <EmptyState
          icon={CheckCircle2}
          title="No losses waiting for review"
          description="Every closed losing position has a review. Nice discipline."
        />
      ) : (
        <ul className="space-y-3">
          {positions.map((p) => (
            <li key={p.id}>
              <Card>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-base font-semibold text-ink">{p.symbol}</span>
                      <StatusBadge position={p} />
                    </div>
                    <div className="num mt-1 text-lg font-semibold text-loss">
                      {formatINR(p.pnl, { signed: true })}{' '}
                      <span className="text-sm font-medium">({formatPct(p.pnl_pct)})</span>
                    </div>
                    <div className="num mt-1 text-xs text-ink-muted">
                      Closed {formatDate(p.closed_on)} · held {formatNumber(p.days_held)} days · in{' '}
                      {formatINR(p.entry_price)} → out {formatINR(p.exit_price)}
                    </div>
                  </div>
                  <Button size="sm" onClick={() => onReview(p)}>
                    Review
                  </Button>
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
