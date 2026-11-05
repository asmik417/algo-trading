import type { PositionFilter } from '../types/ui';
// Tracker queries and mutations. Any position change refreshes lists, stats, loss reviews and the suggestion "tracked" flags.
import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query';
import {
  addPositionNote,
  closePosition,
  createPosition,
  extendPosition,
  getPosition,
  getProfileStats,
  listPositions,
  shortenPosition,
} from '../api/positions';
import type { ChangeExitBody, ClosePositionBody, NoteBody, PositionDetail } from '../types/api';
import { keys } from './queryKeys';

const isSet = (v: number | null | undefined): v is number => v !== null && v !== undefined;

export const usePositions = (
  profileId: number | null | undefined,
  status: PositionFilter = 'all',
) =>
  useQuery({
    queryKey: keys.positions(profileId, status),
    queryFn: () => listPositions(profileId as number, status),
    enabled: isSet(profileId),
  });

export const usePositionDetail = (id: number | null | undefined) =>
  useQuery({
    queryKey: keys.position(id),
    queryFn: () => getPosition(id as number),
    enabled: isSet(id),
  });

export const useProfileStats = (profileId: number | null | undefined) =>
  useQuery({
    queryKey: keys.stats(profileId),
    queryFn: () => getProfileStats(profileId as number),
    enabled: isSet(profileId),
  });

function refreshAfterChange(qc: QueryClient, position?: PositionDetail): void {
  if (position) qc.setQueryData(keys.position(position.id), position);
  for (const key of [
    'positions',
    'stats',
    'suggestions',
    'suggestion',
    'analysis',
    'losses',
    'loss-summary',
    'run-results',
  ]) {
    void qc.invalidateQueries({ queryKey: [key] });
  }
}

export function useCreatePosition() {
  const qc = useQueryClient();
  // The response is a Position without marks/events, so it must not be cached as a PositionDetail.
  return useMutation({ mutationFn: createPosition, onSuccess: () => refreshAfterChange(qc) });
}

export function useExtendPosition() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: ChangeExitBody }) => extendPosition(id, body),
    onSuccess: (p) => refreshAfterChange(qc, p),
  });
}

export function useShortenPosition() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: ChangeExitBody }) => shortenPosition(id, body),
    onSuccess: (p) => refreshAfterChange(qc, p),
  });
}

export function useClosePosition() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: ClosePositionBody }) => closePosition(id, body),
    onSuccess: (p) => refreshAfterChange(qc, p),
  });
}

export function useAddPositionNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: NoteBody }) => addPositionNote(id, body),
    onSuccess: (p) => refreshAfterChange(qc, p),
  });
}
