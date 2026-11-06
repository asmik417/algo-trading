// Explore row tooltips: the decision headline of a stock already analysed, read from the cache (enabled: false, no
// request). Algo Suggested and My Picks rows carry SuggestionSummary.headline themselves.
import { useQueries } from '@tanstack/react-query';
import { analyzeStock } from '../api/stocks';
import { keys } from './queryKeys';

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
