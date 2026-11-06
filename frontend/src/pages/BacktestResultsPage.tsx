// /backtest/:id — progress while it runs, then stat tiles, caveats, equity curve, breakdowns, loss patterns and trades.
import { ArrowLeft } from 'lucide-react';
import { useMemo } from 'react';
import { Link, useParams } from 'react-router-dom';
import { StatusBadge } from '../components/backtest/BacktestList';
import {
  BreakdownTables,
  CaveatsBanner,
  EquityChart,
  LossPatternList,
  StatTiles,
} from '../components/backtest/ResultsParts';
import { TradesTable } from '../components/backtest/TradesTable';
import { RunProgress } from '../components/stocks/RunProgress';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorNotice } from '../components/ui/ErrorNotice';
import { Skeleton } from '../components/ui/Skeleton';
import { isBacktestActive, useBacktest, useBacktestResults } from '../hooks/useBacktests';
import { useReviewTags } from '../hooks/useReviews';
import { BACKTEST_PHASES, settingsLine } from '../lib/backtest';
import { formatDate, formatINR } from '../lib/format';

export default function BacktestResultsPage() {
  const id = Number(useParams().id) || null;
  const bt = useBacktest(id);
  const done = bt.data?.status === 'done';
  const results = useBacktestResults(id, done);
  const tags = useReviewTags();
  const tagLabels = useMemo(
    () => new Map((tags.data ?? []).map((t) => [t.key, t.label])),
    [tags.data],
  );
  const b = results.data?.backtest ?? bt.data;

  return (
    <div className="space-y-4">
      <Link
        to="/backtest"
        className="inline-flex items-center gap-1 text-sm text-ink-muted hover:text-ink"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden /> All backtests
      </Link>
      {bt.error ? (
        <ErrorNotice error={bt.error} onRetry={() => void bt.refetch()} />
      ) : !b ? (
        <Skeleton className="h-40 w-full" />
      ) : (
        <>
          <header className="rounded-lg border border-line bg-white p-4">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-lg font-semibold text-ink">
                Backtest #{b.id} · {b.profile_name}
              </h2>
              <StatusBadge backtest={b} />
            </div>
            <p className="num mt-1 text-sm text-ink-muted">
              {formatDate(b.start_date)} – {formatDate(b.end_date)} · {settingsLine(b)} ·{' '}
              {formatINR(b.capital_per_trade, { digits: 0 })} per trade
              {b.scan_count !== null && ` · ${b.scan_count} scan dates`}
            </p>
            {isBacktestActive(b) && (
              <RunProgress
                run={b}
                label="Backtest progress"
                phaseLabels={BACKTEST_PHASES}
                formatCurrent={(d) => `scan date ${formatDate(d)}`}
                unit="scan dates"
              />
            )}
            {b.status === 'failed' && (
              <p role="alert" className="mt-3 rounded-lg bg-loss-soft px-3 py-2 text-sm text-loss">
                The backtest failed{b.error ? `: ${b.error}` : '.'}
              </p>
            )}
          </header>

          {isBacktestActive(b) ? (
            <EmptyState
              title="Running…"
              description="Results appear here when the backtest finishes. You can leave this page; it keeps running."
            />
          ) : b.status === 'failed' ? null : results.error ? (
            <ErrorNotice error={results.error} onRetry={() => void results.refetch()} />
          ) : !results.data ? (
            <Skeleton className="h-96 w-full" />
          ) : (
            <>
              {results.data.backtest.summary && <StatTiles s={results.data.backtest.summary} />}
              <CaveatsBanner caveats={results.data.backtest.caveats} />
              <EquityChart
                points={results.data.equity_curve}
                maxDrawdownPct={results.data.backtest.summary?.max_drawdown_pct ?? null}
              />
              <div className="grid items-start gap-4 xl:grid-cols-2">
                <BreakdownTables results={results.data} />
                <LossPatternList
                  patterns={results.data.loss_patterns}
                  labels={tagLabels}
                  losses={results.data.backtest.summary?.losses ?? 0}
                />
              </div>
              <TradesTable trades={results.data.trades} tagLabels={tagLabels} />
            </>
          )}
        </>
      )}
    </div>
  );
}
