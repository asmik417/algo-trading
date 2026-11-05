// The algo's suggestion list for a profile, and one suggestion's full detail.
import { useQuery } from '@tanstack/react-query';
import { getSuggestionDetail, getSuggestions } from '../api/suggestions';
import { keys } from './queryKeys';

export const useSuggestions = (
  profileId: number | null | undefined,
  runId: number | 'latest' = 'latest',
) =>
  useQuery({
    queryKey: keys.suggestions(profileId, runId),
    queryFn: () => getSuggestions(profileId as number, runId),
    enabled: profileId !== null && profileId !== undefined,
  });

export const useSuggestionDetail = (id: number | null | undefined) =>
  useQuery({
    queryKey: keys.suggestion(id),
    queryFn: () => getSuggestionDetail(id as number),
    enabled: id !== null && id !== undefined,
  });
