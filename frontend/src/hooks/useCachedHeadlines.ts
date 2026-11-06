// Row tooltips: the decision headline of each row, read from data already fetched (opened dialogs, analyses).
// No request is made here (enabled: false); a row shows its headline once its detail or analysis has been loaded.
import { useQueries } from '@tanstack/react-query';
import { analyzeStock } from '../api/stocks';
import { getSuggestionDetail } from '../api/suggestions';
import { keys } from './queryKeys';

export function useCachedSuggestionHeadlines(ids: number[]): Map<number, string> {
  const results = useQueries({
    queries: ids.map((id) => ({
      queryKey: keys.suggestion(id),
      queryFn: () => getSuggestionDetail(id),
      enabled: false,
    })),
  });
  return new Map(
    ids.flatMap((id, i) =>
      results[i].data ? [[id, results[i].data.decision.headline] as const] : [],
    ),
  );
}

export function useCachedAnalysisHeadlines(
  symbols: string[],
  profileId: number | null | undefined,
): Map<string, string> {
  const results = useQueries({
    queries: symbols.map((symbol) => ({
      queryKey: keys.analysis(symbol, profileId),
      queryFn: () => analyzeStock(symbol, profileId as number),
      enabled: false,
    })),
  });
  return new Map(
    symbols.flatMap((s, i) =>
      results[i].data ? [[s, results[i].data.decision.headline] as const] : [],
    ),
  );
}
