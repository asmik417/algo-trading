// Stocks → Algo Suggested: the list for a profile and the detail behind the stock dialog.
import * as mockDb from '../mocks/db';
import { mockCall } from '../mocks/respond';
import type { SuggestionDetail, SuggestionsResponse } from '../types/api';
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

export const getSuggestionDetail = (id: number): Promise<SuggestionDetail> =>
  USE_MOCKS
    ? mockCall(() => mockDb.getSuggestionDetail(id))
    : http.get<SuggestionDetail>(`/suggestions/${id}`).then((r) => r.data);
