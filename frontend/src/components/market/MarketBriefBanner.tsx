// Top of the Stocks page: today's market regime and stance, with a link to the full brief.
// Hidden while loading and when no brief exists (404), so the page never shows an empty banner.
import { ArrowRight } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useMarketBrief } from '../../hooks/useBrain';
import { REGIME_LABEL, REGIME_TONE } from '../../lib/brain';
import { formatDate } from '../../lib/format';
import { Badge } from '../ui/Badge';

export function MarketBriefBanner() {
  const { data: brief } = useMarketBrief();
  if (!brief) return null;
  return (
    <section
      aria-label="Market brief"
      className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-lg border border-line bg-white px-4 py-3"
    >
      <Badge tone={REGIME_TONE[brief.regime]} className="font-semibold">
        {REGIME_LABEL[brief.regime]}
      </Badge>
      <p className="min-w-0 flex-1 text-sm text-ink" data-testid="market-stance">
        {brief.stance}
      </p>
      <span className="num text-xs text-ink-muted">{formatDate(brief.day)}</span>
      <Link
        to="/market"
        className="inline-flex items-center gap-1 text-sm font-medium text-brand-dark hover:underline"
      >
        Read brief
        <ArrowRight className="h-4 w-4" aria-hidden />
      </Link>
    </section>
  );
}
