// "Why it is listed": the narrated reason, what changed, positives (green ticks) and risks (red marks).
import { Check, X } from 'lucide-react';
import type { Reasons } from '../../types/api';

export function ReasonsPanel({ reasons }: { reasons: Reasons }) {
  return (
    <div className="space-y-4">
      <p className="text-sm leading-relaxed text-ink">{reasons.why_flagged}</p>
      {reasons.what_changed && (
        <p className="rounded-lg bg-slate-50 px-3 py-2 text-sm text-ink-muted">
          <span className="font-medium text-ink">What changed: </span>
          {reasons.what_changed}
        </p>
      )}
      <div className="grid gap-4 md:grid-cols-2">
        <div>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-muted">
            Positives
          </h4>
          {reasons.positives.length === 0 ? (
            <p className="text-sm text-ink-muted">None flagged.</p>
          ) : (
            <ul className="space-y-1.5">
              {reasons.positives.map((t) => (
                <li key={t} className="flex gap-2 text-sm text-ink">
                  <Check className="mt-0.5 h-4 w-4 shrink-0 text-brand" aria-label="Positive" />
                  {t}
                </li>
              ))}
            </ul>
          )}
        </div>
        <div>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-muted">
            Risks
          </h4>
          {reasons.risks.length === 0 ? (
            <p className="text-sm text-ink-muted">None flagged.</p>
          ) : (
            <ul className="space-y-1.5">
              {reasons.risks.map((t) => (
                <li key={t} className="flex gap-2 text-sm text-ink">
                  <X className="mt-0.5 h-4 w-4 shrink-0 text-loss" aria-label="Risk" />
                  {t}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
