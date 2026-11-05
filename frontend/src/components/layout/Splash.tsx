// Full-screen placeholder shown while the app asks the server whether you are signed in.
import { Activity, Loader2 } from 'lucide-react';
import { Button } from '../ui/Button';

export function Splash({ error, onRetry }: { error?: string; onRetry?: () => void }) {
  return (
    <div
      className="flex h-full flex-col items-center justify-center gap-4 bg-page"
      role={error ? 'alert' : 'status'}
    >
      <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-brand text-white">
        <Activity className="h-7 w-7" aria-hidden />
      </span>
      {error ? (
        <>
          <p className="max-w-sm text-center text-sm text-ink-muted">{error}</p>
          {onRetry && (
            <Button variant="secondary" onClick={onRetry}>
              Try again
            </Button>
          )}
        </>
      ) : (
        <p className="flex items-center gap-2 text-sm text-ink-muted">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> Loading…
        </p>
      )}
    </div>
  );
}
