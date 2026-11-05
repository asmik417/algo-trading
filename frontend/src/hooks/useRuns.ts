// Starting an algo run and polling it until it finishes.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';
import { getRun, listRuns, startRun } from '../api/runs';
import type { Run } from '../types/api';
import { keys } from './queryKeys';

const POLL_MS = 2000;

export const isRunActive = (run: Run | undefined): boolean =>
  run?.status === 'queued' || run?.status === 'running';

/** The profile's most recent runs, newest first. Lets a screen notice a run that is already in flight. */
export const useRuns = (profileId: number | null | undefined, limit = 1) =>
  useQuery({
    queryKey: [...keys.runs(profileId), limit],
    queryFn: () => listRuns(profileId as number, limit),
    enabled: profileId !== null && profileId !== undefined,
  });

/** Polls every 2 s while the run is queued or running; refreshes suggestions once it finishes. */
export function useRunStatus(runId: number | null | undefined) {
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: keys.run(runId),
    queryFn: () => getRun(runId as number),
    enabled: runId !== null && runId !== undefined,
    refetchInterval: (q) => (isRunActive(q.state.data) ? POLL_MS : false),
  });
  const status = query.data?.status;
  const profileId = query.data?.profile_id;
  const doneRunId = query.data?.id;
  useEffect(() => {
    if ((status === 'done' || status === 'failed') && profileId !== undefined) {
      void qc.invalidateQueries({ queryKey: ['suggestions', profileId] });
      void qc.invalidateQueries({ queryKey: ['runs', profileId] });
      void qc.invalidateQueries({ queryKey: ['watchlist-runs', profileId] });
      void qc.invalidateQueries({ queryKey: ['run-results', doneRunId] });
    }
  }, [status, profileId, doneRunId, qc]);
  return query;
}

export function useStartRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ profileId, forceRefetch }: { profileId: number; forceRefetch?: boolean }) =>
      startRun(profileId, forceRefetch),
    onSuccess: (run) => {
      qc.setQueryData(keys.run(run.id), run);
      void qc.invalidateQueries({ queryKey: ['runs', run.profile_id] });
    },
  });
}
