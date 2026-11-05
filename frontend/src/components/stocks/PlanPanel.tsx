// "When and at what price to buy" (three entry levels + timing) and "Planned exit" (target, stop, horizon, date).
import clsx from 'clsx';
import { formatDate, formatINR, formatNumber, formatPct } from '../../lib/format';
import type { Plan } from '../../types/api';

const pctFrom = (value: number, base: number): number => ((value - base) / base) * 100;

function EntryCard({
  label,
  price,
  close,
  highlight,
}: {
  label: string;
  price: number;
  close: number;
  highlight?: boolean;
}) {
  return (
    <div
      className={clsx(
        'rounded-lg border p-3',
        highlight ? 'border-brand bg-brand-soft/60' : 'border-line bg-white',
      )}
    >
      <div className="flex items-center justify-between text-xs font-medium uppercase tracking-wide text-ink-muted">
        {label}
        {highlight && (
          <span className="rounded-full bg-brand px-1.5 py-0.5 text-[10px] text-white">
            Recommended
          </span>
        )}
      </div>
      <div className="num mt-1 text-lg font-semibold text-ink">{formatINR(price)}</div>
      <div className="num text-xs text-ink-muted">
        {formatPct(pctFrom(price, close))} vs latest close
      </div>
    </div>
  );
}

function ExitCell({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: 'good' | 'bad';
}) {
  return (
    <div className="rounded-lg border border-line p-3">
      <div className="text-xs font-medium uppercase tracking-wide text-ink-muted">{label}</div>
      <div
        className={clsx(
          'num mt-1 text-lg font-semibold',
          tone === 'good' ? 'text-brand-dark' : tone === 'bad' ? 'text-loss' : 'text-ink',
        )}
      >
        {value}
      </div>
      {sub && <div className="num text-xs text-ink-muted">{sub}</div>}
    </div>
  );
}

export function BuyPlan({ plan, close }: { plan: Plan; close: number }) {
  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-3">
        <EntryCard label="Aggressive" price={plan.entry_aggressive} close={close} />
        <EntryCard label="Optimal" price={plan.entry_optimal} close={close} highlight />
        <EntryCard label="Conservative" price={plan.entry_conservative} close={close} />
      </div>
      <p className="text-sm text-ink">{plan.timing_note}</p>
    </div>
  );
}

export function ExitPlan({ plan }: { plan: Plan }) {
  const entry = plan.entry_optimal;
  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <ExitCell
          label="Target"
          value={formatINR(plan.target)}
          sub={`${formatPct(pctFrom(plan.target, entry))} from optimal entry`}
          tone="good"
        />
        <ExitCell
          label="Stop-loss"
          value={formatINR(plan.stop_loss)}
          sub={`${formatPct(pctFrom(plan.stop_loss, entry))} from optimal entry`}
          tone="bad"
        />
        <ExitCell
          label="Horizon"
          value={`${formatNumber(plan.horizon_days)} days`}
          sub={`Risk-reward ${formatNumber(plan.risk_reward, 1)} : 1`}
        />
        <ExitCell label="Planned exit date" value={formatDate(plan.planned_exit_date)} />
      </div>
      <p className="text-sm text-ink">{plan.exit_note}</p>
    </div>
  );
}
