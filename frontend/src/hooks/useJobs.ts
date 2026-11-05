// Daily monitoring job status and the "Run daily update" action.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getJobStatus, triggerDailyUpdate } from '../api/jobs';
import { keys } from './queryKeys';

export const useJobStatus = () =>
  useQuery({
    queryKey: keys.jobStatus,
    queryFn: getJobStatus,
    // While the job runs, check often; otherwise the footer date barely changes.
    refetchInterval: (q) => (q.state.data?.running ? 2000 : false),
  });

/** Starts the job, then refreshes everything it touches after 3 s (per docs/TASKS_FRONTEND.md). */
export function useRunDailyUpdate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: triggerDailyUpdate,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keys.jobStatus });
      setTimeout(() => {
        for (const key of [
          'job-status',
          'positions',
          'position',
          'stats',
          'losses',
          'loss-summary',
          'suggestions',
        ]) {
          void qc.invalidateQueries({ queryKey: [key] });
        }
      }, 3000);
    },
  });
}
