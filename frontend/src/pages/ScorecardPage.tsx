// Scorecard (/scorecard): how often each logged call was right 20, 40 or 60 sessions later, for the rules and the analyst.
// ?profile=&source=&horizon= hold the controls, so a view can be shared or reloaded.
import { format, parseISO } from 'date-fns';
import { ClipboardCheck } from 'lucide-react';
import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import type { ScorecardHorizon, ScorecardSource } from '../api/scorecard';
import { PageHeader } from '../components/layout/PageHeader';
import { ScorecardTable } from '../components/scorecard/ScorecardTable';
import { WorstMisses } from '../components/scorecard/WorstMisses';
import { SignalBadge } from '../components/stocks/SignalBadge';
import { StockDialog, type StockSelection } from '../components/stocks/StockDialog';
import { Badge } from '../components/ui/Badge';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorNotice } from '../components/ui/ErrorNotice';
import { Select } from '../components/ui/Input';
import { Segmented } from '../components/ui/Segmented';
import { Skeleton } from '../components/ui/Skeleton';
import { Stat } from '../components/ui/Stat';
import { useScorecard } from '../hooks/useScorecard';
import { ACTION_LABEL, ACTION_TONE } from '../lib/brain';
import { pnlClass } from '../lib/colors';
import { formatNumber, formatPct } from '../lib/format';
import { useActiveProfile } from '../store/activeProfile';
import type { AnalystAction } from '../types/brain';

const SOURCES: { value: ScorecardSource; label: string }[] = [
  { value: 'both', label: 'Both' },
  { value: 'rules', label: 'Rules' },
  { value: 'analyst', label: 'Analyst' },
];
const HORIZONS: { value: ScorecardHorizon; label: string }[] = [
  { value: 20, label: '20 sessions' },
  { value: 40, label: '40 sessions' },
  { value: 60, label: '60 sessions' },
];
const SOURCE_LABEL: Record<string, string> = { rules: 'Rules', analyst: 'Analyst' };

const isSource = (v: string | null): v is ScorecardSource =>
  v === 'both' || v === 'rules' || v === 'analyst';
const toHorizon = (v: string | null): ScorecardHorizon => (v === '40' ? 40 : v === '60' ? 60 : 20);
const monthLabel = (key: string) => {
  const d = parseISO(`${key}-01`);
  return Number.isNaN(d.getTime()) ? key : format(d, 'MMM yyyy');
};
const actionKey = (key: string) =>
  key in ACTION_LABEL ? (
    <Badge tone={ACTION_TONE[key as AnalystAction]}>{ACTION_LABEL[key as AnalystAction]}</Badge>
  ) : (
    key
  );

export default function ScorecardPage() {
  const { profile: active, profiles, isLoading: profilesLoading } = useActiveProfile();
  const [params, setParams] = useSearchParams();
  const [selection, setSelection] = useState<StockSelection | null>(null);

  const rawProfile = Number(params.get('profile'));
  const profileId = profiles.some((p) => p.id === rawProfile) ? rawProfile : (active?.id ?? null);
  const rawSource = params.get('source');
  const source: ScorecardSource = isSource(rawSource) ? rawSource : 'both';
  const horizon = toHorizon(params.get('horizon'));
  const profileName = profiles.find((p) => p.id === profileId)?.name ?? '';

  const set = (patch: Record<string, string>) =>
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        Object.entries(patch).forEach(([k, v]) => next.set(k, v));
        return next;
      },
      { replace: true },
    );

  const { data, error, isLoading, isFetching, refetch } = useScorecard(profileId, source, horizon);
  const t = data?.total;
  // Label from the data itself: while the next horizon loads, the previous result stays on screen (dimmed).
  const shown = data?.horizon ?? horizon;

  let body;
  if (profilesLoading || (isLoading && profileId !== null)) {
    body = (
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {Array.from({ length: 4 }, (_, i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
        <Skeleton className="h-64 w-full" />
      </div>
    );
  } else if (profileId === null) {
    body = <EmptyState icon={ClipboardCheck} title="Create a strategy first" />;
  } else if (error) {
    body = <ErrorNotice error={error} onRetry={() => void refetch()} />;
  } else if (!data || !t || t.verdicts === 0) {
    body = (
      <EmptyState
        icon={ClipboardCheck}
        title="Nothing logged yet"
        description={`No ${source === 'both' ? '' : `${SOURCE_LABEL[source].toLowerCase()} `}verdicts have been logged for ${profileName}. Every run, analysis and analyst view is logged, then marked by the daily job.`}
      />
    );
  } else {
    body = (
      <div
        className={isFetching ? 'space-y-4 opacity-70 transition' : 'space-y-4'}
        data-testid="scorecard"
      >
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4" data-testid="scorecard-tiles">
          <Stat label="Verdicts" value={formatNumber(t.verdicts)} sub="logged calls" />
          <Stat
            label="Marked"
            value={formatNumber(t.marked)}
            sub={
              t.verdicts - t.marked > 0
                ? `${formatNumber(t.verdicts - t.marked)} not ${shown} sessions old yet`
                : `all reached ${shown} sessions`
            }
          />
          <Stat
            label="Hit rate"
            value={formatPct(t.hit_rate_pct, { signed: false })}
            sub={`${formatNumber(t.right)} of ${formatNumber(t.marked)} right`}
          />
          <Stat
            label="Average change"
            value={formatPct(t.avg_change_pct)}
            valueClassName={pnlClass(t.avg_change_pct)}
            sub={`price change after ${shown} sessions`}
          />
        </div>
        <div className="grid gap-4 2xl:grid-cols-2">
          <ScorecardTable
            title="By source"
            keyHeader="Source"
            rows={data.by_source}
            renderKey={(k) => SOURCE_LABEL[k] ?? k}
          />
          <ScorecardTable
            title="By action"
            keyHeader="Action"
            rows={data.by_action}
            renderKey={actionKey}
          />
          <ScorecardTable
            title="By signal"
            keyHeader="Signal"
            rows={data.by_signal}
            renderKey={(k) => <SignalBadge signal={k} />}
          />
          <ScorecardTable
            title="By month"
            keyHeader="Month"
            rows={data.by_month}
            renderKey={monthLabel}
          />
        </div>
        <WorstMisses
          verdicts={data.worst}
          horizon={shown}
          onOpen={(symbol) => setSelection({ kind: 'analyze', symbol })}
        />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title="How often each call was right"
        description="Up is right if the price rose, down if it fell, sideways if it moved 5 % or less. Rules and analyst are scored the same way."
      />
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-sm text-ink-muted">
          Strategy
          <Select
            aria-label="Strategy"
            value={profileId ?? ''}
            onChange={(e) => set({ profile: e.target.value })}
            disabled={profiles.length === 0}
          >
            {profiles.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </Select>
        </label>
        <Segmented
          label="Source"
          options={SOURCES}
          value={source}
          onChange={(v) => set({ source: v })}
        />
        <Segmented
          label="Horizon"
          options={HORIZONS}
          value={horizon}
          onChange={(v) => set({ horizon: String(v) })}
        />
      </div>
      {body}
      <StockDialog selection={selection} onClose={() => setSelection(null)} />
    </div>
  );
}
