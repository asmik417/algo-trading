// "Track" for a suggestion; turns into "Tracking" (table) or a link into the Tracker (dialog) once tracked.
import { ArrowRight } from 'lucide-react';
import { Link } from 'react-router-dom';
import type { SuggestionSummary } from '../../types/api';
import { Button } from '../ui/Button';

interface Props {
  suggestion: Pick<SuggestionSummary, 'id' | 'symbol' | 'is_tracked' | 'position_id'>;
  onTrack: () => void;
  loading?: boolean;
  /** "compact" is for table rows; "full" is for the dialog header. */
  variant?: 'compact' | 'full';
  onNavigate?: () => void;
}

export function TrackButton({
  suggestion,
  onTrack,
  loading = false,
  variant = 'compact',
  onNavigate,
}: Props) {
  if (suggestion.is_tracked) {
    if (variant === 'full') {
      return (
        <Link
          to={suggestion.position_id ? `/tracker?position=${suggestion.position_id}` : '/tracker'}
          onClick={onNavigate}
          className="inline-flex h-9 items-center gap-2 rounded-lg border border-brand/40 bg-brand-soft px-4 text-sm font-medium text-brand-dark hover:bg-brand-soft/70"
        >
          Tracked <ArrowRight className="h-4 w-4" aria-hidden /> open in Tracker
        </Link>
      );
    }
    return (
      <Button size="sm" variant="secondary" disabled>
        Tracking
      </Button>
    );
  }
  return (
    <Button
      size={variant === 'full' ? 'md' : 'sm'}
      loading={loading}
      onClick={(e) => {
        e.stopPropagation();
        onTrack();
      }}
    >
      Track
    </Button>
  );
}
