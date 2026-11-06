// Progress bar for any long job (full run, watchlist run, backtest): phase, done / total, and what is being worked on.
import { formatNumber } from '../../lib/format';
import type { RunProgress as Progress, RunStatus } from '../../types/api';

const RUN_PHASES: Record<string, string> = {
  panel: 'Loading market data',
  prefilter: 'Pre-filtering the universe',
  scoring: 'Scoring stocks',
  filtering: 'Applying your filters',
  planning: 'Building entry and exit plans',
  saving: 'Saving results',
  done: 'Finishing',
};

interface Props {
  run: { status: RunStatus; progress: Progress };
  label: string;
  /** Phase names for this kind of job (defaults to algo-run phases). */
  phaseLabels?: Record<string, string>;
  /** How to show `progress.current_symbol` (a symbol for runs, a scan date for backtests). */
  formatCurrent?: (value: string) => string;
  /** Unit for done / total, e.g. "scan dates". */
  unit?: string;
}

export function RunProgress({ run, label, phaseLabels = RUN_PHASES, formatCurrent, unit }: Props) {
  const { phase, done, total, current_symbol } = run.progress;
  const known = total > 0;
  const pct = known ? Math.min(100, Math.round((done / total) * 100)) : 0;
  return (
    <div className="mt-3">
      <div className="mb-1 flex items-center justify-between text-xs text-ink-muted">
        <span>
          {run.status === 'queued' ? 'Queued…' : (phaseLabels[phase] ?? phase)}
          {current_symbol && (
            <span className="num ml-2 font-medium text-ink">
              {formatCurrent ? formatCurrent(current_symbol) : current_symbol}
            </span>
          )}
        </span>
        {known && (
          <span className="num">
            {formatNumber(done)} / {formatNumber(total)}
            {unit ? ` ${unit}` : ''}
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
