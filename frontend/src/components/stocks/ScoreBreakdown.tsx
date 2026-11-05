// The six scoring pillars as bars (score / max) with their weight. Pillars with no data are shown as unavailable, never 0.
import clsx from 'clsx';
import { formatNumber } from '../../lib/format';
import type { PillarScore } from '../../types/api';

export function ScoreBreakdown({ pillars, total }: { pillars: PillarScore[]; total: number }) {
  return (
    <div>
      <div className="mb-3 flex items-baseline justify-between">
        <span className="text-sm text-ink-muted">Total score</span>
        <span className="num text-lg font-semibold text-ink">
          {formatNumber(total, 1)} <span className="text-sm font-normal text-ink-muted">/ 100</span>
        </span>
      </div>
      <ul className="space-y-3">
        {pillars.map((p) => {
          const usable = p.available && p.score !== null;
          const pct = usable && p.max > 0 ? Math.min(100, ((p.score ?? 0) / p.max) * 100) : 0;
          return (
            <li key={p.key}>
              <div className="mb-1 flex items-center justify-between text-sm">
                <span className={clsx(usable ? 'text-ink' : 'text-ink-muted')}>{p.label}</span>
                <span className="num text-ink">
                  {usable ? (
                    <>
                      <strong className="font-semibold">{formatNumber(p.score, 1)}</strong>
                      <span className="text-ink-muted"> / {formatNumber(p.max)}</span>
                    </>
                  ) : (
                    <span className="text-xs italic text-ink-muted">Unavailable — not scored</span>
                  )}
                </span>
              </div>
              <div
                className="h-2 overflow-hidden rounded-full bg-slate-100"
                role="img"
                aria-label={
                  usable ? `${p.label}: ${p.score} of ${p.max}` : `${p.label}: unavailable`
                }
              >
                <div className="h-full rounded-full bg-brand" style={{ width: `${pct}%` }} />
              </div>
              <div className="num mt-0.5 text-xs text-ink-faint">
                Weight {formatNumber(p.weight)}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
