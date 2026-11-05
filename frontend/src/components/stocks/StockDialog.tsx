// The big stock dialog: why it is listed, analysis over time, buy plan, exit plan. Used by both Stocks tabs.
// "suggested" opens a saved suggestion; "analyze" scores any NSE stock on demand under the active strategy.
// The filters panel shows for anything not taken from the algo's own list (Explore and My Picks).
import { CheckCircle2, Info, Loader2, XCircle } from 'lucide-react';
import type { ReactNode } from 'react';
import { useAnalysis } from '../../hooks/useStocks';
import { useSuggestionDetail } from '../../hooks/useSuggestions';
import { useTrackSuggestion } from '../../hooks/useTrackSuggestion';
import { formatINR } from '../../lib/format';
import { useActiveProfile } from '../../store/activeProfile';
import type { SuggestionDetail } from '../../types/api';
import { Dialog } from '../ui/Dialog';
import { ErrorNotice } from '../ui/ErrorNotice';
import { Skeleton } from '../ui/Skeleton';
import { FundamentalsGrid } from './FundamentalsGrid';
import { IndicatorsStrip } from './IndicatorsStrip';
import { BuyPlan, ExitPlan } from './PlanPanel';
import { PriceChart } from './PriceChart';
import { ReasonsPanel } from './ReasonsPanel';
import { ScoreBreakdown } from './ScoreBreakdown';
import { ScoreRing } from './ScoreRing';
import { SignalBadge } from './SignalBadge';
import { TrackButton } from './TrackButton';

export type StockSelection =
  { kind: 'suggested'; id: number; symbol: string } | { kind: 'analyze'; symbol: string };

function Section({ n, title, children }: { n: number; title: string; children: ReactNode }) {
  return (
    <section className="border-t border-line px-5 py-5">
      <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink">
        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-brand-soft text-xs text-brand-dark">
          {n}
        </span>
        {title}
      </h3>
      {children}
    </section>
  );
}

function FiltersPanel({ detail, profileName }: { detail: SuggestionDetail; profileName: string }) {
  const { passed, failures } = detail.filters;
  // When `passed` is true the backend may still list informational notes ("ROE unavailable, filter skipped").
  // They are not failures, so they are shown muted.
  return (
    <div
      className={
        passed
          ? 'mx-5 mb-5 rounded-lg border border-brand/30 bg-brand-soft/60 p-4'
          : 'mx-5 mb-5 rounded-lg border border-loss/30 bg-loss-soft p-4'
      }
      role="status"
    >
      <h3 className="flex items-center gap-2 text-sm font-semibold text-ink">
        {passed ? (
          <CheckCircle2 className="h-4 w-4 text-brand" aria-hidden />
        ) : (
          <XCircle className="h-4 w-4 text-loss" aria-hidden />
        )}
        {passed
          ? `Passes every filter in ${profileName}`
          : `Would not be suggested under ${profileName}`}
      </h3>
      {failures.length > 0 &&
        (passed ? (
          <ul className="mt-2 space-y-0.5 pl-6 text-xs text-ink-muted" aria-label="Notes">
            {failures.map((note) => (
              <li key={note} className="flex gap-1.5">
                <Info className="mt-0.5 h-3 w-3 shrink-0" aria-hidden />
                {note}
              </li>
            ))}
          </ul>
        ) : (
          <ul className="mt-2 list-disc space-y-0.5 pl-9 text-sm text-ink">
            {failures.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
        ))}
    </div>
  );
}

function LoadingBody({ analyzing }: { analyzing: boolean }) {
  return (
    <div className="space-y-4 border-t border-line px-5 py-5" aria-busy="true">
      {analyzing && (
        <p className="flex items-center gap-2 text-sm text-ink-muted" role="status">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          Analysing under your parameters. This can take up to 15 seconds.
        </p>
      )}
      <Skeleton className="h-4 w-3/4" />
      <Skeleton className="h-4 w-1/2" />
      <Skeleton className="h-56 w-full" />
      <div className="grid gap-3 sm:grid-cols-3">
        <Skeleton className="h-20" />
        <Skeleton className="h-20" />
        <Skeleton className="h-20" />
      </div>
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

  return (
    <Dialog
      open={selection !== null}
      onClose={onClose}
      title={selection ? `${selection.symbol} analysis` : 'Stock analysis'}
      hideTitle
    >
      {selection && (
        <>
          <header className="flex flex-wrap items-center gap-x-5 gap-y-3 px-5 py-4 pr-14">
            {detail ? (
              <ScoreRing score={detail.score} />
            ) : (
              <Skeleton className="h-[60px] w-[60px] rounded-full" />
            )}
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-xl font-semibold text-ink">{selection.symbol}</h2>
                {detail && <SignalBadge signal={detail.signal} />}
              </div>
              <div className="mt-0.5 text-sm text-ink-muted">
                {detail ? (
                  `${detail.stage} · ${detail.market_cap_bucket}${detail.sector ? ` · ${detail.sector}` : ''}`
                ) : (
                  <Skeleton className="mt-1 h-4 w-40" />
                )}
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
          </header>

          {query.error ? (
            <div className="border-t border-line px-5 py-5">
              <ErrorNotice error={query.error} onRetry={() => void query.refetch()} />
            </div>
          ) : !detail ? (
            <LoadingBody analyzing={analyzing} />
          ) : (
            <>
              {(analyzing || detail.source !== 'run') && profile && (
                <div className="border-t border-line pt-5">
                  <FiltersPanel detail={detail} profileName={profile.name} />
                </div>
              )}
              <Section n={1} title="Why it is listed">
                <ReasonsPanel reasons={detail.reasons} />
              </Section>
              <Section n={2} title="Analysis over time">
                <div className="grid gap-6 lg:grid-cols-5">
                  <div className="lg:col-span-3">
                    <PriceChart
                      chart={detail.chart}
                      target={detail.plan.target}
                      stopLoss={detail.plan.stop_loss}
                      entry={detail.plan.entry_optimal}
                    />
                  </div>
                  <div className="lg:col-span-2">
                    <ScoreBreakdown pillars={detail.score_breakdown} total={detail.score} />
                  </div>
                </div>
                <div className="mt-5 space-y-3">
                  <IndicatorsStrip data={detail.indicators} />
                  <FundamentalsGrid data={detail.fundamentals} />
                </div>
              </Section>
              <Section n={3} title="When and at what price to buy">
                <BuyPlan plan={detail.plan} close={detail.price} />
              </Section>
              <Section n={4} title="Planned exit">
                <ExitPlan plan={detail.plan} />
              </Section>
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
