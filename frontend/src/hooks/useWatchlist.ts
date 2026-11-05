// My Picks queries and the "Analyse" mutation. Progress polling reuses useRunStatus.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getRunResults, listWatchlistRuns, startWatchlistRun } from '../api/watchlist';
import { keys } from './queryKeys';

const isSet = (v: number | null | undefined): v is number => v !== null && v !== undefined;

export const useWatchlistRuns = (profileId: number | null | undefined, limit = 10) =>
  useQuery({
    queryKey: [...keys.watchlistRuns(profileId), limit],
    queryFn: () => listWatchlistRuns(profileId as number, limit),
    enabled: isSet(profileId),
  });

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
    mutationFn: ({ profileId, symbols }: { profileId: number; symbols: string[] }) =>
      startWatchlistRun(profileId, { symbols }),
    onSuccess: (run) => {
      qc.setQueryData(keys.run(run.id), run);
      void qc.invalidateQueries({ queryKey: ['watchlist-runs', run.profile_id] });
    },
  });
}
