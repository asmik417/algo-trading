// The stock dialog, decision first (contract section "Decision", Dialog layout):
// 1 header with the verdict badge and headline · 2 Our call, then the Analyst view (contract "The brain") · 3 Why ·
// 4 Plan by verdict · 5 Details (collapsed) · 6 disclaimer.
// "suggested" opens a saved suggestion; "analyze" scores any NSE stock on demand under the active strategy.
import { Loader2 } from 'lucide-react';
import { useAnalysis } from '../../hooks/useStocks';
import { useSuggestionDetail } from '../../hooks/useSuggestions';
import { useTrackSuggestion } from '../../hooks/useTrackSuggestion';
import { formatINR } from '../../lib/format';
import { useActiveProfile } from '../../store/activeProfile';
import { Dialog } from '../ui/Dialog';
import { ErrorNotice } from '../ui/ErrorNotice';
import { Skeleton } from '../ui/Skeleton';
import { AnalystViewBlock } from './AnalystViewBlock';
import { DetailsAccordion, OurCall, PlanByVerdict, WhyList } from './DecisionParts';
import { TrackButton } from './TrackButton';
import { OverallBadge } from './VerdictParts';

export type StockSelection =
  { kind: 'suggested'; id: number; symbol: string } | { kind: 'analyze'; symbol: string };

function LoadingBody({ analyzing }: { analyzing: boolean }) {
  return (
    <div className="space-y-4 border-t border-line px-5 py-5" aria-busy="true">
      {analyzing && (
        <p className="flex items-center gap-2 text-sm text-ink-muted" role="status">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          Analysing under your parameters. This can take up to 15 seconds.
        </p>
      )}
      <Skeleton className="h-6 w-2/3" />
      <div className="grid gap-3 md:grid-cols-2">
        <Skeleton className="h-24" />
        <Skeleton className="h-24" />
      </div>
      <Skeleton className="h-28 w-full" />
    </div>
  );
}

export function StockDialog({
  selection,
  onClose,
}: {
  selection: StockSelection | null;
  onClose: () => void;
}) {
  const { profile } = useActiveProfile();
  const { track, isTracking } = useTrackSuggestion();

  const suggested = useSuggestionDetail(selection?.kind === 'suggested' ? selection.id : null);
  const analysis = useAnalysis(
    selection?.kind === 'analyze' ? selection.symbol : null,
    profile?.id,
  );
  const query = selection?.kind === 'analyze' ? analysis : suggested;
  const detail = query.data;
  const analyzing = selection?.kind === 'analyze';
  const sub = detail
    ? [detail.sector, detail.fundamentals.industry, detail.market_cap_bucket]
        .filter((x, i, a) => x && a.indexOf(x) === i)
        .join(' · ')
    : '';

  return (
    <Dialog
      open={selection !== null}
      onClose={onClose}
      title={selection ? `${selection.symbol} analysis` : 'Stock analysis'}
      hideTitle
    >
      {selection && (
        <>
          {/* 1. Header: symbol, sector line, latest close, Track — then the verdict badge and headline. */}
          <header className="px-5 py-4 pr-14">
            <div className="flex flex-wrap items-start gap-x-5 gap-y-2">
              <div className="min-w-0">
                <h2 className="text-xl font-semibold text-ink">{selection.symbol}</h2>
                <div className="mt-0.5 text-sm text-ink-muted">
                  {detail ? sub : <Skeleton className="mt-1 h-4 w-40" />}
                </div>
              </div>
              <div className="ml-auto flex items-center gap-4">
                {detail && (
                  <div className="text-right">
                    <div className="text-xs text-ink-muted">Latest close</div>
                    <div className="num text-lg font-semibold text-ink">
                      {formatINR(detail.price)}
                    </div>
                  </div>
                )}
                {detail && (
                  <TrackButton
                    variant="full"
                    suggestion={detail}
                    loading={isTracking(detail.id)}
                    onTrack={() => void track(detail)}
                    onNavigate={onClose}
                  />
                )}
              </div>
            </div>
            {detail && (
              <div className="mt-3 flex items-center gap-3" data-testid="decision-header">
                <OverallBadge verdict={detail.verdict} large />
                <p className="text-base font-medium leading-snug text-ink">
                  {detail.decision.headline}
                </p>
              </div>
            )}
          </header>

          {query.error ? (
            <div className="border-t border-line px-5 py-5">
              <ErrorNotice error={query.error} onRetry={() => void query.refetch()} />
            </div>
          ) : !detail ? (
            <LoadingBody analyzing={analyzing} />
          ) : (
            <>
              <OurCall decision={detail.decision} />
              <AnalystViewBlock
                key={`${detail.symbol}:${detail.trading_day}:${profile?.id ?? ''}`}
                symbol={detail.symbol}
                day={detail.trading_day}
                profileId={profile?.id}
                embedded={detail.analyst}
              />
              <WhyList decision={detail.decision} />
              <PlanByVerdict detail={detail} />
              <DetailsAccordion detail={detail} />
              <footer className="border-t border-line px-5 py-4">
                <p className="text-xs italic text-ink-muted">{detail.plan.disclaimer}</p>
              </footer>
            </>
          )}
        </>
      )}
    </Dialog>
  );
}
