// The decision-first parts of the stock dialog (contract section "Decision"): Our call, Why, Plan by verdict, Details.
// Details' fourth row is the brain's evidence pack (contract "The brain").
import { ArrowDownRight, ArrowRight, ArrowUpRight, Check, X } from 'lucide-react';
import { Link } from 'react-router-dom';
import { formatDate, formatINR, formatNumber, formatPct } from '../../lib/format';
import type { Decision, Direction, SuggestionDetail } from '../../types/api';
import { Disclosure } from '../ui/Disclosure';
import { EvidencePackPanel } from './EvidencePackPanel';
import { FundamentalsGrid } from './FundamentalsGrid';
import { IndicatorsStrip } from './IndicatorsStrip';
import { BuyPlan, ExitPlan } from './PlanPanel';
import { PriceChart } from './PriceChart';
import { ScoreBreakdown } from './ScoreBreakdown';
import { RulesBadge } from './VerdictParts';

const DIRECTION_WORD: Record<Direction, string> = { up: 'Up', down: 'Down', sideways: 'Sideways' };

function DirectionArrow({ direction }: { direction: Direction }) {
  const cls = 'h-5 w-5 shrink-0';
  if (direction === 'up') return <ArrowUpRight className={`${cls} text-brand`} aria-label="Up" />;
  if (direction === 'down')
    return <ArrowDownRight className={`${cls} text-loss`} aria-label="Down" />;
  return <ArrowRight className={`${cls} text-ink-muted`} aria-label="Sideways" />;
}

/** 2. Our call: expectation and review rule side by side, confidence underneath. */
export function OurCall({ decision }: { decision: Decision }) {
  const { expectation: e, review: r, confidence: c } = decision;
  return (
    <section aria-label="Our call" className="border-t border-line px-5 py-4">
      <h3 className="mb-3 text-sm font-semibold text-ink">Our call</h3>
      <div className="grid gap-3 md:grid-cols-2">
        <div className="rounded-lg border border-line p-3">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-ink-muted">
            Expectation
          </h4>
          <p className="mt-1.5 flex items-center gap-2 text-sm font-semibold text-ink">
            <DirectionArrow direction={e.direction} />
            {DIRECTION_WORD[e.direction]}
            {e.level !== null && (
              <span className="num">to {formatINR(e.level, { digits: 0 })}</span>
            )}
            <span className="num font-normal text-ink-muted">by {formatDate(e.by_date)}</span>
          </p>
          <p className="mt-1 text-sm text-ink">{e.text}</p>
        </div>
        <div className="rounded-lg border border-line p-3">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Review</h4>
          <p className="mt-1.5 text-sm text-ink">
            Do not revisit before <strong className="num">{formatDate(r.until)}</strong> unless{' '}
            {r.trigger}.
          </p>
        </div>
      </div>
      <p className="mt-2 text-xs text-ink-muted" data-testid="confidence">
        {c.signal_win_rate_pct !== null && c.trades !== null ? (
          <>
            In our 12-month backtest this signal won{' '}
            {formatPct(c.signal_win_rate_pct, { signed: false, digits: 0 })} of{' '}
            {formatNumber(c.trades)} trades
            {c.backtest_id !== null && (
              <>
                {' '}
                (
                <Link
                  to={`/backtest/${c.backtest_id}`}
                  className="font-medium text-brand-dark hover:underline"
                >
                  backtest #{c.backtest_id}
                </Link>
                )
              </>
            )}
            .
          </>
        ) : (
          'No backtest track record for this signal yet.'
        )}
      </p>
    </section>
  );
}

/** 3. Why: findings for / against in two columns, then the narrative. */
export function WhyList({ decision }: { decision: Decision }) {
  const forItems = decision.findings.filter((f) => f.side === 'for');
  const against = decision.findings.filter((f) => f.side === 'against');
  const column = (title: string, items: typeof forItems, good: boolean) => (
    <div>
      <h4 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-ink-muted">
        {title}
      </h4>
      {items.length === 0 ? (
        <p className="text-sm text-ink-muted">Nothing {good ? 'in favour' : 'against'}.</p>
      ) : (
        <ul className="space-y-1.5">
          {items.map((f) => (
            <li key={f.text} className="flex gap-2 text-sm text-ink">
              {good ? (
                <Check className="mt-0.5 h-4 w-4 shrink-0 text-brand" aria-label="For" />
              ) : (
                <X className="mt-0.5 h-4 w-4 shrink-0 text-loss" aria-label="Against" />
              )}
              {f.text}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
  return (
    <section aria-label="Why" className="border-t border-line px-5 py-4">
      <h3 className="mb-3 text-sm font-semibold text-ink">Why</h3>
      <div className="grid gap-4 md:grid-cols-2">
        {column('For', forItems, true)}
        {column('Against', against, false)}
      </div>
      <p className="mt-3 text-sm leading-relaxed text-ink" data-testid="narrative">
        {decision.narrative}
      </p>
    </section>
  );
}

/** 4. Plan: in full for Buy, one line (entry cards collapsed) for Watch, collapsed for Avoid. */
export function PlanByVerdict({ detail }: { detail: SuggestionDetail }) {
  const { plan, decision } = detail;
  const full = (
    <div className="space-y-4">
      <BuyPlan plan={plan} close={detail.price} />
      <ExitPlan plan={plan} />
    </div>
  );
  return (
    <section
      aria-label="Plan"
      className="border-t border-line px-5 py-4"
      data-plan={decision.overall}
    >
      {decision.overall === 'buy' ? (
        <>
          <h3 className="mb-3 text-sm font-semibold text-ink">Plan</h3>
          {full}
        </>
      ) : decision.overall === 'watch' ? (
        <>
          <h3 className="mb-1 text-sm font-semibold text-ink">Plan</h3>
          <p className="num text-sm text-ink" data-testid="plan-line">
            Buy zone {formatINR(plan.entry_optimal, { digits: 0 })}, stop{' '}
            {formatINR(plan.stop_loss, { digits: 0 })}, target{' '}
            {formatINR(plan.target, { digits: 0 })}
          </p>
          <Disclosure title="Entry levels and exit plan">{full}</Disclosure>
        </>
      ) : (
        <Disclosure title="Plan if the verdict changes">{full}</Disclosure>
      )}
    </section>
  );
}

/** 5. Details: one accordion, every row collapsed — Rules, Chart & score, Fundamentals, Evidence pack. */
export function DetailsAccordion({ detail }: { detail: SuggestionDetail }) {
  const { rules } = detail.verdict;
  // Anything the filters reported that is not a counted rule failure is an informational "skipped" note.
  const skipped = detail.filters.failures.filter((x) => !rules.failures.includes(x));
  return (
    <section aria-label="Details" className="border-t border-line px-5 py-3">
      <h3 className="pb-1 text-sm font-semibold text-ink">Details</h3>
      <div className="divide-y divide-line/70">
        <Disclosure
          title={
            <>
              Rules {rules.passed}/{rules.total}
            </>
          }
          aside={<RulesBadge rules={rules} />}
        >
          {rules.failures.length === 0 ? (
            <p className="text-sm text-ink">Every rule that could be evaluated passes.</p>
          ) : (
            <ul className="space-y-1">
              {rules.failures.map((f) => (
                <li key={f} className="flex gap-1.5 text-sm text-ink">
                  <X className="mt-0.5 h-4 w-4 shrink-0 text-loss" aria-hidden />
                  {f}
                </li>
              ))}
            </ul>
          )}
          {skipped.length > 0 && (
            <div className="mt-2">
              <h4 className="text-xs font-semibold uppercase tracking-wide text-ink-muted">
                Skipped (no data)
              </h4>
              <ul className="mt-1 space-y-0.5 text-xs text-ink-muted">
                {skipped.map((x) => (
                  <li key={x}>{x}</li>
                ))}
              </ul>
            </div>
          )}
        </Disclosure>
        <Disclosure title="Chart & score">
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
          <div className="mt-4">
            <IndicatorsStrip data={detail.indicators} />
          </div>
        </Disclosure>
        <Disclosure title="Fundamentals">
          <FundamentalsGrid data={detail.fundamentals} />
        </Disclosure>
        <Disclosure title="Evidence pack">
          <EvidencePackPanel symbol={detail.symbol} day={detail.trading_day} />
        </Disclosure>
      </div>
    </section>
  );
}
