// Stocks → My Picks: analyse your own list of stocks under the active strategy, with the same engine and rules as the algo.
// The run id lives in the URL (?tab=picks&run=ID), so a result can be reloaded or reopened from "Previous analyses".
import { ListChecks, Play } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { errorMessage } from '../../api/client';
import { isRunActive, useRunStatus } from '../../hooks/useRuns';
import { useTrackSuggestion } from '../../hooks/useTrackSuggestion';
import { useRunResults, useStartWatchlistRun } from '../../hooks/useWatchlist';
import { formatDate } from '../../lib/format';
import { isMiss } from '../../lib/watchlist';
import type { Profile } from '../../types/api';
import { Button } from '../ui/Button';
import { EmptyState } from '../ui/EmptyState';
import { ErrorNotice } from '../ui/ErrorNotice';
import { Skeleton } from '../ui/Skeleton';
import { useToast } from '../ui/Toast';
import { PreviousAnalyses } from './PreviousAnalyses';
import { RunProgress } from './RunProgress';
import type { StockSelection } from './StockDialog';
import { SymbolPicker } from './SymbolPicker';
import { WatchlistTable } from './WatchlistTable';

const MAX_SYMBOLS = 50;

export function MyPicksTab({
  profile,
  onOpen,
}: {
  profile: Profile;
  onOpen: (s: StockSelection) => void;
}) {
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const [symbols, setSymbols] = useState<string[]>([]);
  const start = useStartWatchlistRun();
  const mounted = useRef(false);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const { track, isTracking } = useTrackSuggestion();

  const requestedRunId = Number(params.get('run')) || null;
  const runQuery = useRunStatus(requestedRunId);
  // A run from another strategy (after switching the active strategy) is not shown.
  const run = runQuery.data && runQuery.data.profile_id === profile.id ? runQuery.data : undefined;
  const runId = run?.id ?? null;
  const active = isRunActive(run);
  const results = useRunResults(runId, { enabled: !!run, live: active });
  const items = results.data?.items ?? [];

  const openRun = (id: number) => setParams({ tab: 'picks', run: String(id) });

  const onAnalyse = async () => {
    try {
      const started = await start.mutateAsync({ profileId: profile.id, symbols });
      // Only jump to the new run if My Picks is still on screen: switching tabs while the request was in flight
      // must not pull the user back. (React Router's setParams(prev => …) sees this component's last render,
      // not the live URL, so a mounted check is the reliable test.) The run stays under "Previous analyses".
      if (mounted.current) openRun(started.id);
      toast.info(
        `Analysing ${symbols.length} stock${symbols.length === 1 ? '' : 's'} under ${profile.name}`,
      );
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };

  const errors = items.filter(isMiss).length;
  const passes = items.filter((i) => !isMiss(i) && i.filters.passed).length;
  const fails = items.length - errors - passes;

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-line bg-white p-4">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-3">
          <h3 className="text-sm font-semibold text-ink">Stocks to analyse</h3>
          <PreviousAnalyses
            profileId={profile.id}
            currentRunId={runId}
            onOpen={(r) => {
              setSymbols(r.symbols ?? []);
              openRun(r.id);
            }}
          />
        </div>
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start">
          <div className="min-w-0 flex-1">
            <SymbolPicker
              value={symbols}
              onChange={setSymbols}
              max={MAX_SYMBOLS}
              disabled={start.isPending}
            />
          </div>
          <Button
            onClick={onAnalyse}
            disabled={symbols.length === 0 || active}
            loading={start.isPending}
            className="h-11 lg:w-36"
          >
            {!start.isPending && <Play className="h-4 w-4" aria-hidden />}
            {active ? 'Analysing…' : 'Analyse'}
          </Button>
        </div>
        {active && run && <RunProgress run={run} label="My Picks analysis progress" />}
        {run?.status === 'failed' && (
          <p role="alert" className="mt-3 rounded-lg bg-loss-soft px-3 py-2 text-sm text-loss">
            The analysis failed{run.error ? `: ${run.error}` : '.'}
          </p>
        )}
      </div>

      {!requestedRunId ? (
        <EmptyState
          icon={ListChecks}
          title="Pick stocks to analyse"
          description={
            <>
              Type symbols above or paste a list like RELIANCE, TCS, INFY. Each one is scored under{' '}
              <strong>{profile.name}</strong> with the same rules as the algo, and you see whether
              it passes your filters.
            </>
          }
        />
      ) : runQuery.error ? (
        <ErrorNotice error={runQuery.error} onRetry={() => void runQuery.refetch()} />
      ) : !run ? (
        runQuery.isLoading ? (
          <Skeleton className="h-40 w-full" />
        ) : (
          <EmptyState
            icon={ListChecks}
            title="That analysis belongs to another strategy"
            description="Pick one from Previous analyses, or start a new one."
          />
        )
      ) : results.error ? (
        <ErrorNotice error={results.error} onRetry={() => void results.refetch()} />
      ) : (
        <>
          <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
            <p className="num text-ink-muted">
              {active
                ? `Analysed ${items.length} of ${run.symbols?.length ?? 0} so far`
                : `Analysed ${run.symbols?.length ?? 0} stocks`}
              {run.trading_day && ` · data as of ${formatDate(run.trading_day)}`}
              {items.length > 0 && (
                <>
                  {' · '}
                  <span className="text-brand-dark">{passes} pass</span> ·{' '}
                  <span className="text-loss">{fails} fail</span>
                  {errors > 0 && ` · ${errors} not found`}
                </>
              )}
            </p>
            {!active && run.symbols && run.symbols.join() !== symbols.join() && (
              <Button size="sm" variant="ghost" onClick={() => setSymbols(run.symbols ?? [])}>
                Edit this list
              </Button>
            )}
          </div>
          {items.length > 0 ? (
            <WatchlistTable
              items={items}
              onOpen={(i) => onOpen({ kind: 'suggested', id: i.id, symbol: i.symbol })}
              onTrack={(i) => void track(i)}
              isTracking={isTracking}
            />
          ) : results.isLoading || active ? (
            <Skeleton className="h-32 w-full" />
          ) : (
            <EmptyState icon={ListChecks} title="No results in this analysis" />
          )}
        </>
      )}
    </div>
  );
}
