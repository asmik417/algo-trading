// Runs: executing the algo for a profile and watching its progress.
import * as mockDb from '../mocks/db';
import { mockCall } from '../mocks/respond';
import type { Run } from '../types/api';
import { USE_MOCKS, http } from './client';

export const startRun = (profileId: number, forceRefetch = false): Promise<Run> =>
  USE_MOCKS
    ? mockCall(() => mockDb.startRun(profileId))
    : http
        .post<Run>(`/profiles/${profileId}/runs`, { force_refetch: forceRefetch })
        .then((r) => r.data);

export const getRun = (runId: number): Promise<Run> =>
  USE_MOCKS
    ? mockCall(() => mockDb.getRun(runId))
    : http.get<Run>(`/runs/${runId}`).then((r) => r.data);

export const listRuns = (profileId: number, limit = 10): Promise<Run[]> =>
  USE_MOCKS
    ? mockCall(() => mockDb.listRuns(profileId, limit))
    : http.get<Run[]>(`/profiles/${profileId}/runs`, { params: { limit } }).then((r) => r.data);
