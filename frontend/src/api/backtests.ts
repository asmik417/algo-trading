// Backtests (the time machine): start one, list them, read one, read its results, delete one.
import * as mockBacktests from '../mocks/backtests';
import { mockCall } from '../mocks/respond';
import type { Backtest, BacktestBody, BacktestResults } from '../types/api';
import { USE_MOCKS, http } from './client';

export const createBacktest = (body: BacktestBody): Promise<Backtest> =>
  USE_MOCKS
    ? mockCall(() => mockBacktests.createBacktest(body))
    : http.post<Backtest>('/backtests', body).then((r) => r.data);

/** Newest first; all strategies when `profileId` is omitted. */
export const listBacktests = (profileId?: number, limit = 20): Promise<Backtest[]> =>
  USE_MOCKS
    ? mockCall(() => mockBacktests.listBacktests(profileId, limit))
    : http
        .get<Backtest[]>('/backtests', { params: { profile_id: profileId, limit } })
        .then((r) => r.data);

export const getBacktest = (id: number): Promise<Backtest> =>
  USE_MOCKS
    ? mockCall(() => mockBacktests.getBacktest(id))
    : http.get<Backtest>(`/backtests/${id}`).then((r) => r.data);

/** 409 while the backtest is not done. */
export const getBacktestResults = (id: number): Promise<BacktestResults> =>
  USE_MOCKS
    ? mockCall(() => mockBacktests.getBacktestResults(id))
    : http.get<BacktestResults>(`/backtests/${id}/results`).then((r) => r.data);

export const deleteBacktest = (id: number): Promise<void> =>
  USE_MOCKS
    ? mockCall(() => mockBacktests.deleteBacktest(id))
    : http.delete(`/backtests/${id}`).then(() => undefined);
