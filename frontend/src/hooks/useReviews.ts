import type { ReviewBody } from '../types/api';
// Loss Analysis queries and mutations.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createReview,
  getLosses,
  getLossSummary,
  listReviewTags,
  updateReview,
} from '../api/reviews';
import { keys } from './queryKeys';

const isSet = (v: number | null | undefined): v is number => v !== null && v !== undefined;

export const useReviewTags = () =>
  useQuery({ queryKey: keys.reviewTags, queryFn: listReviewTags, staleTime: Infinity });

export const useLosses = (profileId: number | null | undefined) =>
  useQuery({
    queryKey: keys.losses(profileId),
    queryFn: () => getLosses(profileId as number),
    enabled: isSet(profileId),
  });

export const useLossSummary = (profileId: number | null | undefined) =>
  useQuery({
    queryKey: keys.lossSummary(profileId),
    queryFn: () => getLossSummary(profileId as number),
    enabled: isSet(profileId),
  });

function useRefreshReviews() {
  const qc = useQueryClient();
  return () => {
    for (const key of ['losses', 'loss-summary', 'stats', 'positions', 'position']) {
      void qc.invalidateQueries({ queryKey: [key] });
    }
  };
}

export function useCreateReview() {
  const refresh = useRefreshReviews();
  return useMutation({
    mutationFn: ({ positionId, body }: { positionId: number; body: ReviewBody }) =>
      createReview(positionId, body),
    onSuccess: refresh,
  });
}

export function useUpdateReview() {
  const refresh = useRefreshReviews();
  return useMutation({
    mutationFn: ({ reviewId, body }: { reviewId: number; body: ReviewBody }) =>
      updateReview(reviewId, body),
    onSuccess: refresh,
  });
}
