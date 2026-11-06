// The scorecard (contract "The brain", Verdict log and scorecard): how often rules and analyst calls were right.
import { mockCall } from '../mocks/respond';
import * as scorecardMock from '../mocks/scorecard';
import type { Scorecard, VerdictSource } from '../types/brain';
import { USE_MOCKS, http } from './client';

export type ScorecardSource = VerdictSource | 'both';
export type ScorecardHorizon = 20 | 40 | 60;

export const getScorecard = (
  profileId: number,
  source: ScorecardSource,
  horizon: ScorecardHorizon,
): Promise<Scorecard> =>
  USE_MOCKS
    ? mockCall(() => scorecardMock.getScorecard(profileId, source, horizon))
    : http
        .get<Scorecard>('/scorecard', { params: { profile_id: profileId, source, horizon } })
        .then((r) => r.data);
