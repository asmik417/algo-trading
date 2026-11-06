// The big stock dialog: why it is listed, analysis over time, buy plan, exit plan. Used by both Stocks tabs.
// "suggested" opens a saved suggestion; "analyze" scores any NSE stock on demand under the active strategy.
// A verdict banner (Overall, reason, Rules and Chart sub-verdicts) sits directly under the header for every stock.
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
import { OverallBadge, RulesBadge, TrendArrow } from './VerdictParts';

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

function VerdictBanner({
  detail,
  strategyName,
}: {
  detail: SuggestionDetail;
  strategyName: string | null;
}) {
  const { verdict, filters } = detail;
  // `filters` may carry informational notes while it passes ("ROE unavailable, filter skipped"): not failures.
  const notes = filters.passed ? filters.failures : [];
  return (
    <section aria-label="Verdict" className="border-t border-line bg-slate-50/60 px-5 py-4">
      <div className="flex flex-wrap items-center gap-3">
        <OverallBadge verdict={verdict} large />
        <p className="min-w-0 flex-1 text-sm text-ink">{verdict.reason}</p>
        {strategyName && <span className="text-xs text-ink-muted">under {strategyName}</span>}
      </div>
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <div className="rounded-lg border border-line bg-white p-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Rules</h3>
            <span className="flex items-center gap-1.5 text-xs text-ink-muted">
              <RulesBadge rules={verdict.rules} /> pass
            </span>
          </div>
          {verdict.rules.failures.length === 0 ? (
            <p className="mt-2 flex items-center gap-1.5 text-sm text-ink">
              <CheckCircle2 className="h-4 w-4 text-brand" aria-hidden /> Every rule that could be
              evaluated passes.
            </p>
          ) : (
            <ul className="mt-2 space-y-1">
              {verdict.rules.failures.map((f) => (
                <li key={f} className="flex gap-1.5 text-sm text-ink">
                  <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-loss" aria-hidden />
                  {f}
                </li>
              ))}
            </ul>
          )}
          {notes.length > 0 && (
            <ul className="mt-2 space-y-0.5 text-xs text-ink-muted" aria-label="Notes">
              {notes.map((note) => (
                <li key={note} className="flex gap-1.5">
                  <Info className="mt-0.5 h-3 w-3 shrink-0" aria-hidden />
                  {note}
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="rounded-lg border border-line bg-white p-3">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Chart</h3>
          <p className="mt-2 flex items-center gap-1.5 text-sm font-medium text-ink">
            <TrendArrow trend={verdict.chart.trend} />
            {verdict.chart.label}
          </p>
          {verdict.chart.points.length > 0 && (
            <ul className="mt-1.5 flex flex-wrap gap-1.5">
              {verdict.chart.points.map((pt) => (
                <li
                  key={pt}
                  className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-ink-muted"
                >
                  {pt}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
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
              <VerdictBanner detail={detail} strategyName={profile?.name ?? null} />
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
              {detail.verdict.overall === 'avoid' && (
                <p
                  role="note"
                  className="flex items-center gap-2 border-t border-line bg-slate-50 px-5 py-3 text-sm font-medium text-ink-muted"
                >
                  <Info className="h-4 w-4 shrink-0" aria-hidden />
                  Plan shown for reference only; the verdict is Avoid.
                </p>
              )}
              <div
                className={detail.verdict.overall === 'avoid' ? 'opacity-50' : undefined}
                data-testid="plan-sections"
              >
                <Section n={3} title="When and at what price to buy">
                  <BuyPlan plan={detail.plan} close={detail.price} />
                </Section>
                <Section n={4} title="Planned exit">
                  <ExitPlan plan={detail.plan} />
                </Section>
              </div>
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
