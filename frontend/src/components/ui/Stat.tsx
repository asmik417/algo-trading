// A labelled number tile for stats rows.
import clsx from 'clsx';
import type { ReactNode } from 'react';

export function Stat({
  label,
  value,
  sub,
  valueClassName,
  onClick,
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  valueClassName?: string;
  onClick?: () => void;
}) {
  const body = (
    <>
      <div className="text-xs font-medium uppercase tracking-wide text-ink-muted">{label}</div>
      <div className={clsx('num mt-1 text-xl font-semibold text-ink', valueClassName)}>{value}</div>
      {sub && <div className="num mt-0.5 text-xs text-ink-muted">{sub}</div>}
    </>
  );
  const base = 'rounded-lg border border-line bg-white p-4 text-left';
  return onClick ? (
    <button
      type="button"
      onClick={onClick}
      className={clsx(
        base,
        'transition hover:border-brand focus:outline-none focus-visible:ring-2 focus-visible:ring-brand/40',
      )}
    >
      {body}
    </button>
  ) : (
    <div className={base}>{body}</div>
  );
}
