// Market brief (/market): the day's regime, facts, paragraph, leading and lagging indices and the market backdrop,
// plus the past briefs. ?day=YYYY-MM-DD picks one; otherwise the latest is shown.
import clsx from 'clsx';
import { Newspaper, TrendingDown, TrendingUp } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';
import { PageHeader } from '../components/layout/PageHeader';
import { MarketContextTiles } from '../components/market/MarketContextTiles';
import { Badge } from '../components/ui/Badge';
import { Card } from '../components/ui/Card';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorNotice } from '../components/ui/ErrorNotice';
import { Skeleton } from '../components/ui/Skeleton';
import { useMarketBrief, useMarketBriefs } from '../hooks/useBrain';
import { REGIME_LABEL, REGIME_TONE } from '../lib/brain';
import { pnlClass } from '../lib/colors';
import { formatDate, formatDateTime, formatPct } from '../lib/format';
import type { MarketBrief } from '../types/brain';

function IndexList({
  title,
  rows,
  up,
}: {
  title: string;
  rows: MarketBrief['leaders'];
  up: boolean;
}) {
  const Icon = up ? TrendingUp : TrendingDown;
  return (
    <div>
      <h4 className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-ink-muted">
        <Icon className={clsx('h-4 w-4', up ? 'text-brand' : 'text-loss')} aria-hidden />
        {title}
      </h4>
      {rows.length === 0 ? (
        <p className="text-sm text-ink-muted">Unavailable</p>
      ) : (
        <ul className="space-y-1">
          {rows.map((r) => (
            <li key={r.index} className="flex justify-between gap-3 text-sm text-ink">
              <span>{r.index}</span>
              <span className={clsx('num font-medium', pnlClass(r.change_1w_pct))}>
                {formatPct(r.change_1w_pct)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function BriefView({ brief }: { brief: MarketBrief }) {
  return (
    <div className="space-y-4" data-testid="market-brief" data-day={brief.day}>
      <Card>
        <div className="flex flex-wrap items-center gap-3">
          <Badge tone={REGIME_TONE[brief.regime]} className="px-3 py-1 text-sm font-semibold">
            {REGIME_LABEL[brief.regime]}
          </Badge>
          <p className="text-base font-medium text-ink">{brief.stance}</p>
        </div>
        <p className="mt-3 text-sm leading-relaxed text-ink">{brief.paragraph}</p>
        <h4 className="mt-4 text-xs font-semibold uppercase tracking-wide text-ink-muted">Facts</h4>
        <ul className="mt-1.5 list-disc space-y-1 pl-5 text-sm text-ink" data-testid="brief-facts">
          {brief.facts.map((f) => (
            <li key={f}>{f}</li>
          ))}
        </ul>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <IndexList title="Leaders this week" rows={brief.leaders} up />
          <IndexList title="Laggards this week" rows={brief.laggards} up={false} />
        </div>
        <p className="mt-4 text-xs text-ink-muted">
          Every number comes from the day&apos;s market data; the text is written from those
          numbers. Written {formatDateTime(brief.created_at)}.
        </p>
      </Card>
      <div>
        <h3 className="mb-2 text-sm font-semibold text-ink">Market backdrop</h3>
        <MarketContextTiles context={brief.context} />
      </div>
    </div>
  );
}

export default function MarketPage() {
  const [params, setParams] = useSearchParams();
  const day = params.get('day');
  const briefs = useMarketBriefs(10);
  const brief = useMarketBrief(day);
  const shownDay = brief.data?.day ?? null;

  const body = brief.error ? (
    <ErrorNotice error={brief.error} onRetry={() => void brief.refetch()} />
  ) : brief.isLoading ? (
    <Skeleton className="h-72 w-full" />
  ) : brief.data ? (
    <BriefView brief={brief.data} />
  ) : (
    <EmptyState
      icon={Newspaper}
      title={day ? `No market brief for ${formatDate(day)}` : 'No market brief yet'}
      description="The nightly job writes one after the market closes."
    />
  );

  return (
    <div className="space-y-4">
      <PageHeader
        title={shownDay ? `Market brief for ${formatDate(shownDay)}` : 'Market brief'}
        description="How the whole market stands today, and what that means for new buys."
      />
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_16rem]">
        <div className="min-w-0">{body}</div>
        <aside aria-label="Past briefs">
          <h3 className="mb-2 text-sm font-semibold text-ink">Past briefs</h3>
          {briefs.error ? (
            <ErrorNotice error={briefs.error} onRetry={() => void briefs.refetch()} />
          ) : briefs.isLoading ? (
            <Skeleton className="h-40 w-full" />
          ) : !briefs.data?.length ? (
            <p className="text-sm text-ink-muted">None yet.</p>
          ) : (
            <ul className="space-y-1.5">
              {briefs.data.map((b) => (
                <li key={b.day}>
                  <button
                    type="button"
                    aria-current={b.day === shownDay ? 'true' : undefined}
                    onClick={() => setParams(b.day === briefs.data?.[0]?.day ? {} : { day: b.day })}
                    className={clsx(
                      'w-full rounded-lg border px-3 py-2 text-left transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand/40',
                      b.day === shownDay
                        ? 'border-brand bg-brand-soft/40'
                        : 'border-line bg-white hover:border-brand',
                    )}
                  >
                    <span className="flex items-center justify-between gap-2">
                      <span className="num text-sm font-medium text-ink">{formatDate(b.day)}</span>
                      <Badge tone={REGIME_TONE[b.regime]}>{REGIME_LABEL[b.regime]}</Badge>
                    </span>
                    <span className="mt-0.5 block truncate text-xs text-ink-muted" title={b.stance}>
                      {b.stance}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </aside>
      </div>
    </div>
  );
}
