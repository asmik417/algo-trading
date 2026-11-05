// My Picks: run the algo on a chosen list of symbols, read the results, list earlier runs.
import * as mockDb from '../mocks/db';
import { mockCall } from '../mocks/respond';
import type { Run, WatchlistResults, WatchlistRunBody } from '../types/api';
import { USE_MOCKS, http } from './client';

export const startWatchlistRun = (profileId: number, body: WatchlistRunBody): Promise<Run> =>
  USE_MOCKS
    ? mockCall(() => mockDb.startWatchlistRun(profileId, body))
    : http.post<Run>(`/profiles/${profileId}/watchlist-runs`, body).then((r) => r.data);

export const getRunResults = (runId: number): Promise<WatchlistResults> =>
  USE_MOCKS
    ? mockCall(() => mockDb.getRunResults(runId))
    : http.get<WatchlistResults>(`/runs/${runId}/results`).then((r) => r.data);

export const listWatchlistRuns = (profileId: number, limit = 10): Promise<Run[]> =>
  USE_MOCKS
    ? mockCall(() => mockDb.listWatchlistRuns(profileId, limit))
    : http
        .get<Run[]>(`/profiles/${profileId}/watchlist-runs`, { params: { limit } })
        .then((r) => r.data);
