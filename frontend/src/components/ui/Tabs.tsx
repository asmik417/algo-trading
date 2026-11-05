// Underlined tab strip. Controlled: the parent owns the selected key.
import clsx from 'clsx';

export interface TabItem<K extends string> {
  key: K;
  label: string;
  count?: number;
}

export function Tabs<K extends string>({
  tabs,
  value,
  onChange,
  label,
}: {
  tabs: TabItem<K>[];
  value: K;
  onChange: (key: K) => void;
  label: string;
}) {
  return (
    <div role="tablist" aria-label={label} className="flex gap-6 border-b border-line">
      {tabs.map((t) => {
        const active = t.key === value;
        return (
          <button
            key={t.key}
            role="tab"
            type="button"
            aria-selected={active}
            onClick={() => onChange(t.key)}
            className={clsx(
              '-mb-px flex items-center gap-2 border-b-2 px-1 pb-2.5 pt-1 text-sm font-medium transition',
              active
                ? 'border-brand text-brand-dark'
                : 'border-transparent text-ink-muted hover:text-ink',
            )}
          >
            {t.label}
            {t.count !== undefined && (
              <span
                className={clsx(
                  'rounded-full px-1.5 text-xs',
                  active ? 'bg-brand-soft text-brand-dark' : 'bg-slate-100 text-ink-muted',
                )}
              >
                {t.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
