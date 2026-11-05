// Top of Loss Analysis: how many losses, how many reviewed, average loss, and which mistake tags keep coming back.
import { formatPct } from '../../lib/format';
import type { LossSummary } from '../../types/api';
import { Card } from '../ui/Card';
import { Skeleton } from '../ui/Skeleton';
import { Stat } from '../ui/Stat';

export function TagSummary({
  summary,
  loading,
}: {
  summary: LossSummary | undefined;
  loading: boolean;
}) {
  if (loading || !summary) return <Skeleton className="h-40 w-full" />;
  const max = Math.max(1, ...summary.by_tag.map((t) => t.count));
  return (
    <div className="grid gap-3 lg:grid-cols-[repeat(3,minmax(0,1fr))_minmax(0,2fr)]">
      <Stat label="Losing trades" value={summary.total_losses} />
      <Stat
        label="Reviewed"
        value={`${summary.reviewed} / ${summary.total_losses}`}
        sub={
          summary.total_losses > summary.reviewed
            ? `${summary.total_losses - summary.reviewed} waiting`
            : 'All reviewed'
        }
      />
      <Stat
        label="Average loss"
        value={formatPct(summary.avg_loss_pct)}
        valueClassName={summary.avg_loss_pct === null ? undefined : 'text-loss'}
      />
      <Card title="What keeps going wrong" className="lg:row-span-1">
        {summary.by_tag.length === 0 ? (
          <p className="text-sm text-ink-muted">Tag counts appear here once you review a loss.</p>
        ) : (
          <ul className="space-y-2">
            {summary.by_tag.map((t) => (
              <li key={t.key} className="flex items-center gap-3 text-sm">
                <span className="w-44 shrink-0 truncate text-ink" title={t.label}>
                  {t.label}
                </span>
                <div
                  className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100"
                  role="img"
                  aria-label={`${t.label}: ${t.count}`}
                >
                  <div
                    className="h-full rounded-full bg-loss/80"
                    style={{ width: `${(t.count / max) * 100}%` }}
                  />
                </div>
                <span className="num w-5 text-right font-medium text-ink">{t.count}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
