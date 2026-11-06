// The stock dialog's "Analyst view" (contract "The brain", Frontend): the model's opinion over the evidence pack,
// shown under "Our call" and kept apart from the rules verdict. It never changes a score, level or date.
import { AlertTriangle, Check, Loader2, Minus, Sparkles, X } from 'lucide-react';
import { useAnalyst } from '../../hooks/useBrain';
import {
  ACTION_LABEL,
  ACTION_TONE,
  CONFIDENCE_LABEL,
  CONFIDENCE_TONE,
  EVIDENCE_LABEL,
  EVIDENCE_TONE,
} from '../../lib/brain';
import { formatDate, formatDateTime } from '../../lib/format';
import type { AnalystView } from '../../types/api';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { ErrorNotice } from '../ui/ErrorNotice';
import { Skeleton } from '../ui/Skeleton';

function AgreesChip({ agrees }: { agrees: boolean | null }) {
  if (agrees === null)
    return (
      <Badge tone="grey" className="gap-1">
        <Minus className="h-3.5 w-3.5" aria-hidden />
        No rules verdict to compare
      </Badge>
    );
  return agrees ? (
    <Badge tone="green" className="gap-1">
      <Check className="h-3.5 w-3.5" aria-hidden />
      Agrees with rules
    </Badge>
  ) : (
    <Badge tone="amber" className="gap-1">
      <X className="h-3.5 w-3.5" aria-hidden />
      Does not agree with rules
    </Badge>
  );
}

function ViewBody({ view: v }: { view: AnalystView }) {
  return (
    <div className="space-y-3" data-testid="analyst-view" data-audited={v.audited}>
      <div className="flex flex-wrap items-center gap-2">
        <span data-testid="analyst-action">
          <Badge tone={ACTION_TONE[v.action]} className="px-2.5 font-semibold">
            {ACTION_LABEL[v.action]}
          </Badge>
        </span>
        <Badge tone={CONFIDENCE_TONE[v.confidence]}>{CONFIDENCE_LABEL[v.confidence]}</Badge>
        <span data-testid="agrees-chip">
          <AgreesChip agrees={v.agrees_with_rules} />
        </span>
      </div>

      {!v.audited && (
        <div
          role="alert"
          data-testid="audit-warning"
          className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900"
        >
          <p className="flex items-start gap-2 font-medium">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            Some numbers in this view could not be matched to the evidence pack. Treat it with extra
            caution.
          </p>
          {v.audit_notes.length > 0 && (
            <ul className="mt-1.5 list-disc space-y-0.5 pl-11 text-xs">
              {v.audit_notes.map((n) => (
                <li key={n}>{n}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div data-testid="anomalies">
        <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-ink-muted">
          Anomalies
        </h4>
        {v.anomalies.length === 0 ? (
          <p className="text-sm text-ink-muted">Nothing unusual in the evidence.</p>
        ) : (
          <ul className="space-y-1">
            {v.anomalies.map((a) => (
              <li key={a} className="flex gap-2 text-sm text-ink">
                <AlertTriangle
                  className="mt-0.5 h-4 w-4 shrink-0 text-amber-600"
                  aria-label="Anomaly"
                />
                {a}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <div className="rounded-lg border border-line p-3" data-testid="bull-case">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-brand-dark">
            Bull case
          </h4>
          <p className="mt-1 text-sm text-ink">{v.bull_case}</p>
        </div>
        <div className="rounded-lg border border-line p-3" data-testid="bear-case">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-loss">Bear case</h4>
          <p className="mt-1 text-sm text-ink">{v.bear_case}</p>
        </div>
      </div>

      {v.tests.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-line">
          <table className="min-w-full text-sm" aria-label="Tests">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-ink-muted">
              <tr>
                <th scope="col" className="px-3 py-2 text-left font-medium">
                  Test
                </th>
                <th scope="col" className="px-3 py-2 text-left font-medium">
                  Evidence
                </th>
                <th scope="col" className="px-3 py-2 text-left font-medium">
                  Note
                </th>
              </tr>
            </thead>
            <tbody>
              {v.tests.map((t) => (
                <tr key={t.claim} className="border-t border-line/70 align-top">
                  <td className="px-3 py-2 text-ink">{t.claim}</td>
                  <td className="px-3 py-2">
                    <Badge tone={EVIDENCE_TONE[t.evidence]}>{EVIDENCE_LABEL[t.evidence]}</Badge>
                  </td>
                  <td className="px-3 py-2 text-ink-muted">{t.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="space-y-1 text-sm text-ink">
        <p data-testid="analyst-trigger">
          <span className="font-medium">Would change its mind if:</span> {v.trigger}
        </p>
        <p data-testid="analyst-want-to-know">
          <span className="font-medium">Would like to know:</span> {v.want_to_know}
        </p>
      </div>
      <p className="text-xs text-ink-muted">
        An opinion over the evidence pack for {formatDate(v.day)}, over the next{' '}
        {v.horizon_sessions} sessions. The rules verdict above is unchanged by it; both are scored
        on the scorecard. {v.model}, {formatDateTime(v.created_at)}.
      </p>
    </div>
  );
}

export function AnalystViewBlock({
  symbol,
  day,
  profileId,
  embedded,
}: {
  symbol: string;
  /** The detail's trading day: the view is for that day. */
  day: string;
  profileId: number | null | undefined;
  /** The detail's `analyst` field; undefined when the backend did not send one. */
  embedded: AnalystView | null | undefined;
}) {
  const { view, run, canRun, starting, runError, waiting, gaveUp } = useAnalyst(
    symbol,
    day,
    profileId,
    embedded,
  );

  let body;
  if (view.error) {
    body = <ErrorNotice error={view.error} onRetry={() => void view.refetch()} />;
  } else if (view.data) {
    body = <ViewBody view={view.data} />;
  } else if (view.data === undefined) {
    body = <Skeleton className="h-20 w-full" />;
  } else if (waiting) {
    body = (
      <p
        className="flex items-center gap-2 text-sm text-ink-muted"
        role="status"
        data-testid="analyst-waiting"
      >
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
        The analyst is reading the evidence pack. This usually takes under a minute.
      </p>
    );
  } else {
    body = (
      <div className="space-y-2" data-testid="analyst-empty">
        <p className="text-sm text-ink-muted">
          {gaveUp
            ? 'Still not ready after 3 minutes. It will appear here once the analyst finishes; check again later.'
            : `No analyst view for ${symbol} on ${formatDate(day)} yet.`}
        </p>
        {runError !== null && <ErrorNotice error={runError} />}
        <Button
          size="sm"
          variant="secondary"
          onClick={run}
          loading={starting}
          disabled={!canRun}
          data-testid="run-analyst"
        >
          <Sparkles className="h-4 w-4" aria-hidden />
          {gaveUp ? 'Check again' : 'Run analyst'}
        </Button>
      </div>
    );
  }

  return (
    <section aria-label="Analyst view" className="border-t border-line px-5 py-4">
      <h3 className="mb-3 text-sm font-semibold text-ink">Analyst view</h3>
      {body}
    </section>
  );
}
