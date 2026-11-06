// Stocks → My Picks: named pick lists (contract "Pick lists"), each analysed under the active strategy with the same
// engine and rules as the algo. The chosen list is remembered in localStorage (picks.selectedListId). Analyse always
// saves the list first, then runs it by list_id. A run opened from "Previous analyses" lives in the URL (?run=ID).
import { ListChecks, Play, Save } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { errorMessage } from '../../api/client';
import { useCreatePickList, usePickLists, useUpdatePickList } from '../../hooks/usePickLists';
import { isRunActive, useRunStatus } from '../../hooks/useRuns';
import { useTrackSuggestion } from '../../hooks/useTrackSuggestion';
import { useRunResults, useStartWatchlistRun, useWatchlistRuns } from '../../hooks/useWatchlist';
import { formatDate } from '../../lib/format';
import { isMiss } from '../../lib/watchlist';
import { useSelectedPickListId } from '../../store/selectedPickList';
import type { Overall, PickList, Profile } from '../../types/api';
import { Button } from '../ui/Button';
import { EmptyState } from '../ui/EmptyState';
import { ErrorNotice } from '../ui/ErrorNotice';
import { Skeleton } from '../ui/Skeleton';
import { useToast } from '../ui/Toast';
import { MAX_LIST_NAME, NEW_LIST, PickListBar } from './PickListBar';
import { PreviousAnalyses } from './PreviousAnalyses';
import { RunProgress } from './RunProgress';
import type { StockSelection } from './StockDialog';
import { SymbolPicker } from './SymbolPicker';
import { WatchlistTable } from './WatchlistTable';

const MAX_SYMBOLS = 50;
const sameSymbols = (a: string[], b: string[]) =>
  a.length === b.length && a.every((s, i) => s === b[i]);

/** "List <n>" with the first n that is not already taken (names are unique, case-insensitive). */
function suggestedName(lists: PickList[]): string {
  const taken = new Set(lists.map((l) => l.name.trim().toLowerCase()));
  let n = lists.length + 1;
  while (taken.has(`list ${n}`)) n++;
  return `List ${n}`;
}

export function MyPicksTab({
  profile,
  onOpen,
}: {
  profile: Profile;
  onOpen: (s: StockSelection) => void;
}) {
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const listsQuery = usePickLists();
  const lists = listsQuery.data ?? [];
  const [storedId, setStoredId] = useSelectedPickListId();
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState<string | null>(null);
  const createList = useCreatePickList();
  const updateList = useUpdatePickList();
  const start = useStartWatchlistRun();
  const { track, isTracking } = useTrackSuggestion();
  const mounted = useRef(false);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  // The stored list, else the most recently updated one; "New list…" (or no lists at all) means creating.
  const selected = creating ? null : (lists.find((l) => l.id === storedId) ?? lists[0] ?? null);
  const name = newName ?? suggestedName(lists);

  // Edited symbols belong to one version of one list: saving (new updated_at) or switching lists resets them.
  // Start with no key, so a list that is already cached at mount (e.g. back from another tab) shows its symbols.
  const draftKey = selected ? `${selected.id}:${selected.updated_at}` : NEW_LIST;
  const [draft, setDraft] = useState<{ key: string; symbols: string[] }>({ key: '', symbols: [] });
  const symbols = draft.key === draftKey ? draft.symbols : (selected?.symbols ?? []);
  const setSymbols = (next: string[]) => setDraft({ key: draftKey, symbols: next });
  const dirty = selected ? !sameSymbols(symbols, selected.symbols) : symbols.length > 0;
  const nameValid =
    selected !== null || (name.trim().length > 0 && name.trim().length <= MAX_LIST_NAME);

  // Run shown: one opened from the URL if it belongs to this list and strategy, else the list's latest run.
  const latest = useWatchlistRuns(profile.id, {
    limit: 1,
    listId: selected?.id,
    enabled: !!selected,
  });
  const requestedId = Number(params.get('run')) || null;
  const requested = useRunStatus(requestedId).data;
  const requestedFits =
    !!requested &&
    !!selected &&
    requested.profile_id === profile.id &&
    requested.list_id === selected.id;
  const shownId = selected ? (requestedFits ? requestedId : (latest.data?.[0]?.id ?? null)) : null;
  const runQuery = useRunStatus(shownId);
  const run =
    runQuery.data && selected && runQuery.data.list_id === selected.id ? runQuery.data : undefined;
  const active = isRunActive(run);
  const results = useRunResults(run?.id ?? null, { enabled: !!run, live: active });
  const items = results.data?.items ?? [];

  const busy = createList.isPending || updateList.isPending || start.isPending;
  const clearRun = () => setParams({ tab: 'picks' }, { replace: true });

  const selectList = (id: number | typeof NEW_LIST) => {
    if (id === NEW_LIST) {
      setCreating(true);
      setNewName(null);
      // Every new list starts empty (the "new" draft key is shared, so clear what an earlier new list left behind).
      setDraft({ key: NEW_LIST, symbols: [] });
    } else {
      setCreating(false);
      setStoredId(id);
    }
    clearRun();
  };

  /** Saves the list (create or update) and returns it; null when saving failed (already reported). */
  const save = async (): Promise<PickList | null> => {
    try {
      if (!selected) {
        const created = await createList.mutateAsync({ name: name.trim(), symbols });
        setCreating(false);
        setNewName(null);
        setStoredId(created.id);
        return created;
      }
      if (!dirty) return selected;
      return await updateList.mutateAsync({ id: selected.id, body: { symbols } });
    } catch (e) {
      toast.error(errorMessage(e));
      return null;
    }
  };

  const onSave = async () => {
    const saved = await save();
    if (saved) toast.success(`Saved ${saved.name} (${saved.symbols.length} stocks)`);
  };

  const onAnalyse = async () => {
    const saved = await save();
    if (!saved) return;
    try {
      const started = await start.mutateAsync({
        profileId: profile.id,
        body: { list_id: saved.id },
      });
      // Only jump to the new run if My Picks is still on screen (switching tabs mid-request must not pull the
      // user back; React Router's setParams sees this component's last render, so check mounted instead).
      if (mounted.current) setParams({ tab: 'picks', run: String(started.id) });
      toast.info(`Analysing ${saved.name} (${saved.symbols.length} stocks) under ${profile.name}`);
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };

  const errors = items.filter(isMiss).length;
  const countOf = (o: Overall) => items.filter((i) => !isMiss(i) && i.verdict.overall === o).length;

  if (listsQuery.isLoading) return <Skeleton className="h-40 w-full" />;
  if (listsQuery.error)
    return <ErrorNotice error={listsQuery.error} onRetry={() => void listsQuery.refetch()} />;

  return (
    <div className="space-y-4">
      <div className="space-y-3 rounded-lg border border-line bg-white p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0 flex-1">
            <PickListBar
              lists={lists}
              selected={selected}
              newName={name}
              onNewNameChange={setNewName}
              onSelect={selectList}
              onDeleted={() => {
                setStoredId(null);
                setDraft({ key: NEW_LIST, symbols: [] });
                clearRun();
              }}
              disabled={busy}
            />
          </div>
          {selected && (
            <PreviousAnalyses
              profileId={profile.id}
              listId={selected.id}
              currentRunId={run?.id ?? null}
              onOpen={(r) => setParams({ tab: 'picks', run: String(r.id) })}
            />
          )}
        </div>
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start">
          <div className="min-w-0 flex-1">
            <SymbolPicker value={symbols} onChange={setSymbols} max={MAX_SYMBOLS} disabled={busy} />
          </div>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              onClick={onSave}
              disabled={!dirty || symbols.length === 0 || !nameValid || busy}
              loading={(createList.isPending || updateList.isPending) && !start.isPending}
              className="h-11"
            >
              <Save className="h-4 w-4" aria-hidden /> Save list
            </Button>
            <Button
              onClick={onAnalyse}
              disabled={symbols.length === 0 || !nameValid || active || busy}
              loading={start.isPending}
              className="h-11 lg:w-36"
            >
              {!start.isPending && <Play className="h-4 w-4" aria-hidden />}
              {active ? 'Analysing…' : 'Analyse'}
            </Button>
          </div>
        </div>
        {active && run && <RunProgress run={run} label="My Picks analysis progress" />}
        {run?.status === 'failed' && (
          <p role="alert" className="rounded-lg bg-loss-soft px-3 py-2 text-sm text-loss">
            The analysis failed{run.error ? `: ${run.error}` : '.'}
          </p>
        )}
      </div>

      {!selected ? (
        <EmptyState
          icon={ListChecks}
          title="Name your list and add stocks"
          description={
            <>
              Type symbols above or paste a list like RELIANCE, TCS, INFY, then Save list or
              Analyse. Each stock is scored under <strong>{profile.name}</strong> with the same
              rules as the algo and gets a verdict: Buy, Watch or Avoid.
            </>
          }
        />
      ) : latest.isLoading || (shownId !== null && runQuery.isLoading) ? (
        <Skeleton className="h-40 w-full" />
      ) : latest.error || runQuery.error ? (
        <ErrorNotice error={latest.error ?? runQuery.error} onRetry={() => void latest.refetch()} />
      ) : !run ? (
        <EmptyState
          icon={ListChecks}
          title={`No analysis of ${selected.name} under ${profile.name} yet`}
          description={`Press Analyse to score these ${selected.symbols.length} stocks with the same rules as the algo.`}
        />
      ) : results.error ? (
        <ErrorNotice error={results.error} onRetry={() => void results.refetch()} />
      ) : (
        <>
          <p className="num text-sm text-ink-muted">
            {active
              ? `Analysed ${items.length} of ${run.symbols?.length ?? 0} so far`
              : `Analysed ${run.symbols?.length ?? 0} stocks`}
            {run.trading_day && ` · data as of ${formatDate(run.trading_day)}`}
            {items.length > 0 && (
              <>
                {' · '}
                <span className="text-brand-dark">{countOf('buy')} buy</span> ·{' '}
                <span className="text-amber-700">{countOf('watch')} watch</span> ·{' '}
                <span className="text-loss">{countOf('avoid')} avoid</span>
                {errors > 0 && ` · ${errors} not found`}
              </>
            )}
          </p>
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
