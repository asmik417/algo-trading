// A row of toggle chips for picking several options (review tags, market-cap buckets).
import clsx from 'clsx';
import { Check } from 'lucide-react';

export interface ChipOption {
  value: string;
  label: string;
}

export function ChipGroup({
  options,
  selected,
  onChange,
  label,
}: {
  options: ChipOption[];
  selected: string[];
  onChange: (next: string[]) => void;
  label: string;
}) {
  const toggle = (value: string) =>
    onChange(selected.includes(value) ? selected.filter((v) => v !== value) : [...selected, value]);
  return (
    <div role="group" aria-label={label} className="flex flex-wrap gap-2">
      {options.map((o) => {
        const on = selected.includes(o.value);
        return (
          <button
            key={o.value}
            type="button"
            aria-pressed={on}
            onClick={() => toggle(o.value)}
            className={clsx(
              'inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand/40',
              on
                ? 'border-brand bg-brand-soft font-medium text-brand-dark'
                : 'border-line bg-white text-ink-muted hover:border-slate-300 hover:text-ink',
            )}
          >
            {on && <Check className="h-3.5 w-3.5" aria-hidden />}
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
