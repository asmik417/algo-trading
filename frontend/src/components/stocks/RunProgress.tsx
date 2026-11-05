// Progress bar for any run (full or watchlist): phase, done / total, and the symbol being worked on.
import { formatNumber } from '../../lib/format';
import type { Run } from '../../types/api';

const PHASE_LABEL: Record<string, string> = {
  panel: 'Loading market data',
  prefilter: 'Pre-filtering the universe',
  scoring: 'Scoring stocks',
  filtering: 'Applying your filters',
  planning: 'Building entry and exit plans',
  saving: 'Saving results',
  done: 'Finishing',
};

export function RunProgress({ run, label }: { run: Run; label: string }) {
  const { phase, done, total, current_symbol } = run.progress;
  const known = total > 0;
  const pct = known ? Math.min(100, Math.round((done / total) * 100)) : 0;
  return (
    <div className="mt-3">
      <div className="mb-1 flex items-center justify-between text-xs text-ink-muted">
        <span>
          {run.status === 'queued' ? 'Queued…' : (PHASE_LABEL[phase] ?? phase)}
          {current_symbol && (
            <span className="num ml-2 font-medium text-ink">{current_symbol}</span>
          )}
        </span>
        {known && (
          <span className="num">
            {formatNumber(done)} / {formatNumber(total)}
          </span>
        )}
      </div>
      <div
        className="h-2 overflow-hidden rounded-full bg-slate-100"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={known ? pct : undefined}
        aria-label={label}
      >
        <div
          className={
            known
              ? 'h-full rounded-full bg-brand transition-all'
              : 'h-full w-1/4 animate-pulse rounded-full bg-brand/60'
          }
          style={known ? { width: `${pct}%` } : undefined}
        />
      </div>
    </div>
  );
}
