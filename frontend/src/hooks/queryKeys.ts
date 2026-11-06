import type { PositionFilter, StockQuery } from '../types/ui';
// One place for every TanStack Query key, so invalidation after a mutation can never miss a screen.

export const keys = {
  health: ['health'] as const,
  jobStatus: ['job-status'] as const,
  paramSpec: ['param-spec'] as const,
  profiles: ['profiles'] as const,
  runs: (profileId: number | null | undefined) => ['runs', profileId] as const,
  watchlistRuns: (profileId: number | null | undefined) => ['watchlist-runs', profileId] as const,
  pickLists: ['pick-lists'] as const,
  runResults: (runId: number | null | undefined) => ['run-results', runId] as const,
  run: (runId: number | null | undefined) => ['run', runId] as const,
  suggestions: (profileId: number | null | undefined, runId: number | 'latest' = 'latest') =>
    ['suggestions', profileId, runId] as const,
  suggestion: (id: number | null | undefined) => ['suggestion', id] as const,
  stocks: (query: StockQuery) => ['stocks', query] as const,
  stock: (symbol: string | null | undefined) => ['stock', symbol] as const,
  analysis: (symbol: string | null | undefined, profileId: number | null | undefined) =>
    ['analysis', symbol, profileId] as const,
  positions: (profileId: number | null | undefined, status: PositionFilter) =>
    ['positions', profileId, status] as const,
  position: (id: number | null | undefined) => ['position', id] as const,
  stats: (profileId: number | null | undefined) => ['stats', profileId] as const,
  reviewTags: ['review-tags'] as const,
  losses: (profileId: number | null | undefined) => ['losses', profileId] as const,
  marketBrief: (day: string | null | undefined) => ['market-brief', day ?? 'latest'] as const,
  marketBriefs: (limit: number) => ['market-briefs', limit] as const,
  evidence: (symbol: string | null | undefined, day: string | null | undefined) =>
    ['evidence', symbol, day] as const,
  /** Views are cached per (symbol, day, strategy), so the strategy is part of the key. */
  analystView: (
    symbol: string | null | undefined,
    day: string | null | undefined,
    profileId: number | null | undefined,
  ) => ['analyst-view', symbol, day, profileId] as const,
  scorecard: (profileId: number | null | undefined, source: string, horizon: number) =>
    ['scorecard', profileId, source, horizon] as const,
  lossSummary: (profileId: number | null | undefined) => ['loss-summary', profileId] as const,
};
