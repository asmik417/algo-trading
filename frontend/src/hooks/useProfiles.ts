import type { UpdateProfileBody } from '../types/api';
// Profile queries and mutations.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  activateProfile,
  createProfile,
  deleteProfile,
  getParamSpec,
  listProfiles,
  updateProfile,
} from '../api/profiles';
import { keys } from './queryKeys';

export const useProfiles = () => useQuery({ queryKey: keys.profiles, queryFn: listProfiles });

/** The form definition rarely changes, so keep it for the whole session. */
export const useParamSpec = () =>
  useQuery({ queryKey: keys.paramSpec, queryFn: getParamSpec, staleTime: Infinity });

export function useCreateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createProfile,
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.profiles }),
  });
}

export function useUpdateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: UpdateProfileBody }) => updateProfile(id, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.profiles }),
  });
}

export function useDeleteProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteProfile,
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.profiles }),
  });
}

export function useActivateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: activateProfile,
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.profiles }),
  });
}
