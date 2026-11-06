// "The brain": market briefs, a stock's evidence pack (with on-demand build) and its analyst view
// (with "Run analyst", which polls GET analyst-view until the queued view exists).
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import {
  buildEvidence,
  getAnalystView,
  getEvidence,
  getMarketBrief,
  listMarketBriefs,
  runAnalystView,
} from '../api/brain';
import { isApiError } from '../api/client';
import type { AnalystView } from '../types/api';
import { keys } from './queryKeys';

/** A 404 means "none exists yet" for these resources, which is a normal state, not an error. */
async function orNullOn404<T>(load: () => Promise<T>): Promise<T | null> {
  try {
    return await load();
  } catch (e) {
    if (isApiError(e) && e.status === 404) return null;
    throw e;
  }
}

export const POLL_MS = 2000;
/** Give up polling after this long; the nightly job may still produce the view. */
export const POLL_LIMIT_MS = 3 * 60 * 1000;

/** null when no brief exists (404); the banner then stays hidden. */
export const useMarketBrief = (day?: string | null) =>
  useQuery({
    queryKey: keys.marketBrief(day),
    queryFn: () => orNullOn404(() => getMarketBrief(day ?? undefined)),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

export const useMarketBriefs = (limit = 10) =>
  useQuery({
    queryKey: keys.marketBriefs(limit),
    queryFn: () => orNullOn404(() => listMarketBriefs(limit)),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

/** Only mounted while the Details row is open, so the pack is fetched lazily. null = not built (404). */
export const useEvidence = (symbol: string, day: string) =>
  useQuery({
    queryKey: keys.evidence(symbol, day),
    queryFn: () => orNullOn404(() => getEvidence(symbol, day)),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

export function useBuildEvidence(symbol: string, day: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => buildEvidence(symbol),
    onSuccess: (pack) => qc.setQueryData(keys.evidence(symbol, day), pack),
  });
}

/**
 * The analyst view for (symbol, day, strategy). `embedded` is the detail's `analyst` field: when present it seeds the
 * cache with no request; when the backend left it out (undefined), GET analyst-view is asked instead.
 * After "Run analyst" answers `queued`, GET is polled every 2 s until the view exists (or POLL_LIMIT_MS passes).
 */
export function useAnalyst(
  symbol: string,
  day: string,
  profileId: number | null | undefined,
  embedded: AnalystView | null | undefined,
) {
  const qc = useQueryClient();
  const key = keys.analystView(symbol, day, profileId);
  // idle → (POST answered "queued") polling → view arrives, or timedOut after POLL_LIMIT_MS.
  const [phase, setPhase] = useState<'idle' | 'polling' | 'timedOut'>('idle');

  useEffect(() => {
    if (phase !== 'polling') return;
    const timer = setTimeout(() => setPhase('timedOut'), POLL_LIMIT_MS);
    return () => clearTimeout(timer);
  }, [phase]);

  const view = useQuery({
    queryKey: key,
    queryFn: () => orNullOn404(() => getAnalystView(symbol, day, profileId ?? undefined)),
    initialData: embedded,
    staleTime: 60 * 1000,
    retry: false,
    refetchInterval: (q) => (phase === 'polling' && !q.state.data ? POLL_MS : false),
  });

  const run = useMutation({
    mutationFn: () => runAnalystView(symbol, profileId as number),
    onSuccess: (result) => {
      if ('status' in result) setPhase('polling');
      else qc.setQueryData(key, result);
    },
  });

  return {
    view,
    run: () => run.mutate(),
    canRun: profileId !== null && profileId !== undefined,
    starting: run.isPending,
    runError: run.error,
    waiting: phase === 'polling' && !view.data,
    gaveUp: phase === 'timedOut' && !view.data,
  };
}
