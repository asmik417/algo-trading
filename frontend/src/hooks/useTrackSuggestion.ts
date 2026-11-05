// "Track" button logic shared by the Suggested table and the stock dialog.
// Always sends { profile_id, suggestion_id } (docs/API_CONTRACT.md: "Ad-hoc analysis is persisted"); never a bare symbol.
import { errorMessage } from '../api/client';
import { formatINR } from '../lib/format';
import { useToast } from '../components/ui/Toast';
import { useActiveProfile } from '../store/activeProfile';
import type { SuggestionSummary } from '../types/api';
import { useCreatePosition } from './usePositions';

export function useTrackSuggestion() {
  const { profile } = useActiveProfile();
  const create = useCreatePosition();
  const toast = useToast();

  const track = async (suggestion: Pick<SuggestionSummary, 'id' | 'symbol'>): Promise<void> => {
    if (!profile) return;
    try {
      const position = await create.mutateAsync({
        profile_id: profile.id,
        suggestion_id: suggestion.id,
      });
      toast.success(
        `Tracking ${suggestion.symbol} with ${formatINR(position.capital, { digits: 0 })}`,
      );
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };

  return {
    track,
    /** True while this particular suggestion is being tracked. */
    isTracking: (suggestionId: number): boolean =>
      create.isPending && create.variables?.suggestion_id === suggestionId,
  };
}
