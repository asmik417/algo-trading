// "The brain" (contract section of that name): market briefs, a stock's evidence pack and its analyst view.
// The analyst never computes: everything here is read-only text and numbers the backend already produced.
import * as brainMock from '../mocks/brain';
import * as mockDb from '../mocks/db';
import { mockCall } from '../mocks/respond';
import type { AnalystRunResult, AnalystView, EvidencePack, MarketBrief } from '../types/api';
import { USE_MOCKS, http } from './client';

const stockPath = (symbol: string, rest: string) => `/stocks/${encodeURIComponent(symbol)}/${rest}`;

/** GET /market/brief: the latest brief, or the one for `day`. 404 when none exists. */
export const getMarketBrief = (day?: string): Promise<MarketBrief> =>
  USE_MOCKS
    ? mockCall(() => brainMock.getMarketBrief(day))
    : http.get<MarketBrief>('/market/brief', { params: day ? { day } : {} }).then((r) => r.data);

/** GET /market/briefs: newest first. */
export const listMarketBriefs = (limit = 10): Promise<MarketBrief[]> =>
  USE_MOCKS
    ? mockCall(() => brainMock.listMarketBriefs(limit))
    : http.get<MarketBrief[]>('/market/briefs', { params: { limit } }).then((r) => r.data);

/** GET /stocks/{symbol}/evidence: 404 when no pack has been built for that day. */
export const getEvidence = (symbol: string, day?: string): Promise<EvidencePack> =>
  USE_MOCKS
    ? mockCall(() => mockDb.getEvidence(symbol, day))
    : http
        .get<EvidencePack>(stockPath(symbol, 'evidence'), { params: day ? { day } : {} })
        .then((r) => r.data);

/** POST /stocks/{symbol}/evidence: builds a pack on demand (synchronous, under 10 s) → 201. */
export const buildEvidence = (symbol: string): Promise<EvidencePack> =>
  USE_MOCKS
    ? mockCall(() => mockDb.buildEvidence(symbol), 1200)
    : http.post<EvidencePack>(stockPath(symbol, 'evidence')).then((r) => r.data);

/** GET /stocks/{symbol}/analyst-view: the view for (day, strategy); the backend defaults to the active strategy. 404 if none. */
export const getAnalystView = (
  symbol: string,
  day?: string,
  profileId?: number,
): Promise<AnalystView> =>
  USE_MOCKS
    ? mockCall(() => mockDb.getAnalystView(symbol, day, profileId))
    : http
        .get<AnalystView>(stockPath(symbol, 'analyst-view'), {
          params: {
            ...(day ? { day } : {}),
            ...(profileId !== undefined ? { profile_id: profileId } : {}),
          },
        })
        .then((r) => r.data);

/** POST /stocks/{symbol}/analyst-view: 202 { status: 'queued' }, or 200 with the view if one exists for the day. */
export const runAnalystView = (symbol: string, profileId: number): Promise<AnalystRunResult> =>
  USE_MOCKS
    ? mockCall(() => mockDb.requestAnalystView(symbol, profileId))
    : http
        .post<AnalystRunResult>(stockPath(symbol, 'analyst-view'), null, {
          params: { profile_id: profileId },
        })
        .then((r) => r.data);
