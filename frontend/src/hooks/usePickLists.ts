// Pick list queries and mutations. Renames and deletes also refresh run lists (runs show the list's current name).
import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query';
import { createPickList, deletePickList, listPickLists, updatePickList } from '../api/pickLists';
import type { UpdatePickListBody } from '../types/api';
import { keys } from './queryKeys';

export const usePickLists = () => useQuery({ queryKey: keys.pickLists, queryFn: listPickLists });

function refresh(qc: QueryClient): void {
  void qc.invalidateQueries({ queryKey: keys.pickLists });
  void qc.invalidateQueries({ queryKey: ['watchlist-runs'] });
  void qc.invalidateQueries({ queryKey: ['run'] });
}

export function useCreatePickList() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: createPickList, onSuccess: () => refresh(qc) });
}

export function useUpdatePickList() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: UpdatePickListBody }) =>
      updatePickList(id, body),
    onSuccess: () => refresh(qc),
  });
}

export function useDeletePickList() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: deletePickList, onSuccess: () => refresh(qc) });
}
