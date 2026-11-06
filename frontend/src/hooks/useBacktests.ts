// Backtest queries and mutations. Lists and single backtests poll every 2 s while anything is queued or running.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createBacktest,
  deleteBacktest,
  getBacktest,
  getBacktestResults,
  listBacktests,
} from '../api/backtests';
import type { Backtest } from '../types/api';

export const isBacktestActive = (b: Pick<Backtest, 'status'> | undefined): boolean =>
  b?.status === 'queued' || b?.status === 'running';

export const useBacktests = (profileId?: number, limit = 20) =>
  useQuery({
    queryKey: ['backtests', profileId ?? 'all', limit],
    queryFn: () => listBacktests(profileId, limit),
    refetchInterval: (q) => (q.state.data?.some(isBacktestActive) ? 2000 : false),
  });

export const useBacktest = (id: number | null) =>
  useQuery({
    queryKey: ['backtest', id],
    queryFn: () => getBacktest(id as number),
    enabled: id !== null,
    refetchInterval: (q) => (isBacktestActive(q.state.data) ? 2000 : false),
  });

/** Only fetched once the backtest is done (the endpoint answers 409 before that). */
export const useBacktestResults = (id: number | null, done: boolean) =>
  useQuery({
    queryKey: ['backtest-results', id],
    queryFn: () => getBacktestResults(id as number),
    enabled: id !== null && done,
    staleTime: Infinity,
  });

export function useCreateBacktest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createBacktest,
    onSuccess: (b) => {
      qc.setQueryData(['backtest', b.id], b);
      void qc.invalidateQueries({ queryKey: ['backtests'] });
    },
  });
}

export function useDeleteBacktest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteBacktest,
    onSuccess: (_v, id) => {
      qc.removeQueries({ queryKey: ['backtest', id] });
      qc.removeQueries({ queryKey: ['backtest-results', id] });
      void qc.invalidateQueries({ queryKey: ['backtests'] });
    },
  });
}
