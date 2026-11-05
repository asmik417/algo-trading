import type { StockQuery } from '../types/ui';
// Explore tab: the NSE list, one stock's chart, and on-demand analysis under a profile.
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { analyzeStock, getStock, listStocks } from '../api/stocks';
import { keys } from './queryKeys';

/** Keeps the previous page on screen while the next one loads, so paging and typing do not flash. */
export const useStocks = (query: StockQuery, options: { enabled?: boolean } = {}) =>
  useQuery({
    queryKey: keys.stocks(query),
    queryFn: () => listStocks(query),
    placeholderData: keepPreviousData,
    enabled: options.enabled ?? true,
  });

export const useStockDetail = (symbol: string | null | undefined) =>
  useQuery({
    queryKey: keys.stock(symbol),
    queryFn: () => getStock(symbol as string),
    enabled: !!symbol,
  });

/** POST /stocks/{symbol}/analyze, treated as a query so reopening the dialog is instant. */
export const useAnalysis = (
  symbol: string | null | undefined,
  profileId: number | null | undefined,
) =>
  useQuery({
    queryKey: keys.analysis(symbol, profileId),
    queryFn: () => analyzeStock(symbol as string, profileId as number),
    enabled: !!symbol && profileId !== null && profileId !== undefined,
    staleTime: 5 * 60 * 1000,
  });
