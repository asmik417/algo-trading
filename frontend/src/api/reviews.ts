// Loss Analysis: tags, pending and reviewed losses, and the per-tag summary.
import * as mockDb from '../mocks/db';
import { mockCall } from '../mocks/respond';
import type { LossSummary, LossesResponse, Review, ReviewBody, ReviewTag } from '../types/api';
import { USE_MOCKS, http } from './client';

export const listReviewTags = (): Promise<ReviewTag[]> =>
  USE_MOCKS
    ? mockCall(() => mockDb.listReviewTags())
    : http.get<ReviewTag[]>('/reviews/tags').then((r) => r.data);

export const getLosses = (profileId: number): Promise<LossesResponse> =>
  USE_MOCKS
    ? mockCall(() => mockDb.getLosses(profileId))
    : http.get<LossesResponse>(`/profiles/${profileId}/losses`).then((r) => r.data);

export const getLossSummary = (profileId: number): Promise<LossSummary> =>
  USE_MOCKS
    ? mockCall(() => mockDb.getLossSummary(profileId))
    : http.get<LossSummary>(`/profiles/${profileId}/losses/summary`).then((r) => r.data);

export const createReview = (positionId: number, body: ReviewBody): Promise<Review> =>
  USE_MOCKS
    ? mockCall(() => mockDb.createReview(positionId, body))
    : http.post<Review>(`/positions/${positionId}/review`, body).then((r) => r.data);

export const updateReview = (reviewId: number, body: ReviewBody): Promise<Review> =>
  USE_MOCKS
    ? mockCall(() => mockDb.updateReview(reviewId, body))
    : http.put<Review>(`/reviews/${reviewId}`, body).then((r) => r.data);
