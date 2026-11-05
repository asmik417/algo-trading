// Frontend-only query/response shapes that the contract describes in prose but keeps out of its TypeScript block.
// Entity and request-body types live in ./api.ts (copied verbatim from the contract).

export type PositionFilter = 'open' | 'due' | 'closed' | 'all';

export type StockSortKey =
  | 'symbol'
  | 'close'
  | 'change_1d_pct'
  | 'change_1w_pct'
  | 'change_1m_pct'
  | 'change_3m_pct'
  | 'dist_from_52w_high_pct'
  | 'volume_ratio_20d'
  | 'avg_turnover_lacs';

export interface StockQuery {
  search?: string;
  sort?: StockSortKey;
  order?: 'asc' | 'desc';
  limit?: number;
  offset?: number;
}

export interface DailyUpdateStarted {
  started: boolean;
  reason?: string;
}
