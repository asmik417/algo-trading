// My Picks queries and the "Analyse" mutation. Progress polling reuses useRunStatus.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getRunResults, listWatchlistRuns, startWatchlistRun } from '../api/watchlist';
import type { WatchlistRunBody } from '../types/api';
import { keys } from './queryKeys';

const isSet = (v: number | null | undefined): v is number => v !== null && v !== undefined;

/** Watchlist runs of the profile, optionally only those of one pick list (newest first). */
export const useWatchlistRuns = (
  profileId: number | null | undefined,
  options: { limit?: number; listId?: number | null; enabled?: boolean } = {},
) => {
  const { limit = 10, listId, enabled = true } = options;
  return useQuery({
    queryKey: [...keys.watchlistRuns(profileId), limit, listId ?? 'all'],
    queryFn: () => listWatchlistRuns(profileId as number, limit, listId ?? undefined),
    enabled: isSet(profileId) && enabled,
  });
};

/** Results of one watchlist run. While the run is in progress they grow symbol by symbol, so poll every 2 s. */
export const useRunResults = (
  runId: number | null | undefined,
  options: { enabled: boolean; live: boolean },
) =>
  useQuery({
    queryKey: keys.runResults(runId),
    queryFn: () => getRunResults(runId as number),
    enabled: isSet(runId) && options.enabled,
    refetchInterval: options.live ? 2000 : false,
  });

export function useStartWatchlistRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ profileId, body }: { profileId: number; body: WatchlistRunBody }) =>
      startWatchlistRun(profileId, body),
    onSuccess: (run) => {
      qc.setQueryData(keys.run(run.id), run);
      void qc.invalidateQueries({ queryKey: ['watchlist-runs', run.profile_id] });
    },
  });
}
