import type { StockQuery } from '../types/ui';
// Stocks → Explore: the whole NSE universe, one stock's chart, and on-demand analysis under a profile.
import * as mockDb from '../mocks/db';
import { mockCall } from '../mocks/respond';
import type { StockDetail, StocksResponse, SuggestionDetail } from '../types/api';
import { USE_MOCKS, http } from './client';

export const listStocks = (query: StockQuery = {}): Promise<StocksResponse> =>
  USE_MOCKS
    ? mockCall(() => mockDb.listStocks(query))
    : http.get<StocksResponse>('/stocks', { params: query }).then((r) => r.data);

export const getStock = (symbol: string): Promise<StockDetail> =>
  USE_MOCKS
    ? mockCall(() => mockDb.getStock(symbol))
    : http.get<StockDetail>(`/stocks/${encodeURIComponent(symbol)}`).then((r) => r.data);

/** Can take 5-15 s on the real backend (one fundamentals fetch). The mock waits 1.5 s to feel similar. */
export const analyzeStock = (symbol: string, profileId: number): Promise<SuggestionDetail> =>
  USE_MOCKS
    ? mockCall(() => mockDb.analyzeStock(symbol, profileId), 1500)
    : http
        .post<SuggestionDetail>(`/stocks/${encodeURIComponent(symbol)}/analyze`, null, {
          params: { profile_id: profileId },
        })
        .then((r) => r.data);
