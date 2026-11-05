// Inline error with an optional retry button, for failed queries.
import { AlertTriangle } from 'lucide-react';
import { errorMessage } from '../../api/client';
import { Button } from './Button';

export function ErrorNotice({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div
      role="alert"
      className="flex items-start gap-3 rounded-lg border border-loss/30 bg-loss-soft p-4 text-sm text-loss"
    >
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <div className="flex-1">{errorMessage(error)}</div>
      {onRetry && (
        <Button size="sm" variant="secondary" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}
