// Stocks → Algo Suggested: the list for a profile and the detail behind the stock dialog.
import * as mockDb from '../mocks/db';
import { mockCall } from '../mocks/respond';
import type { SuggestionDetail, SuggestionsResponse } from '../types/api';
import type { WithAnalyst } from '../types/brain';
import { USE_MOCKS, http } from './client';

export const getSuggestions = (
  profileId: number,
  runId: number | 'latest' = 'latest',
): Promise<SuggestionsResponse> =>
  USE_MOCKS
    ? mockCall(() => mockDb.getSuggestions(profileId, runId))
    : http
        .get<SuggestionsResponse>(`/profiles/${profileId}/suggestions`, {
          params: { run_id: runId },
        })
        .then((r) => r.data);

/** Carries `analyst` per "The brain" (an older backend leaves it out; the dialog then asks GET analyst-view). */
export const getSuggestionDetail = (id: number): Promise<WithAnalyst<SuggestionDetail>> =>
  USE_MOCKS
    ? mockCall(() => mockDb.getSuggestionDetail(id))
    : http.get<WithAnalyst<SuggestionDetail>>(`/suggestions/${id}`).then((r) => r.data);
