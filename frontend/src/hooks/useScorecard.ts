// The scorecard for one strategy, source and horizon; the previous result stays on screen while the next loads.
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { getScorecard, type ScorecardHorizon, type ScorecardSource } from '../api/scorecard';
import { keys } from './queryKeys';

export const useScorecard = (
  profileId: number | null | undefined,
  source: ScorecardSource,
  horizon: ScorecardHorizon,
) =>
  useQuery({
    queryKey: keys.scorecard(profileId, source, horizon),
    queryFn: () => getScorecard(profileId as number, source, horizon),
    enabled: profileId !== null && profileId !== undefined,
    placeholderData: keepPreviousData,
  });
