// The "Scoring weights" section: one number per pillar with a live total that turns red unless it is exactly 100.
import clsx from 'clsx';
import { useId } from 'react';
import type { ParamSection, ParamSpec } from '../../types/api';
import { NumberBox } from './ParamFieldControl';
import { WEIGHTS_TOTAL, weightsTotal, type Draft, type DraftValue } from './paramDraft';

export function WeightsEditor({
  spec,
  section,
  draft,
  errors,
  onChange,
}: {
  spec: ParamSpec;
  section: ParamSection;
  draft: Draft;
  errors: Record<string, string>;
  onChange: (key: string, value: DraftValue) => void;
}) {
  const baseId = useId();
  const total = weightsTotal(spec, draft);
  const ok = total === WEIGHTS_TOTAL;
  return (
    <div>
      <ul className="space-y-3">
        {section.fields.map((field) => {
          const value = draft[field.key];
          const share =
            typeof value === 'number' && total > 0
              ? Math.max(0, Math.min(100, (value / total) * 100))
              : 0;
          const inputId = `${baseId}-${field.key}`;
          return (
            <li key={field.key}>
              <div className="flex items-center gap-3">
                <label htmlFor={inputId} className="w-48 shrink-0 text-sm text-ink">
                  {field.label}
                </label>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100" aria-hidden>
                  <div
                    className={clsx('h-full rounded-full', ok ? 'bg-brand' : 'bg-loss/70')}
                    style={{ width: `${share}%` }}
                  />
                </div>
                <NumberBox
                  id={inputId}
                  field={field}
                  value={value ?? null}
                  onChange={(v) => onChange(field.key, v)}
                  invalid={!!errors[field.key]}
                  className="w-20 text-right"
                />
              </div>
              {errors[field.key] && (
                <p className="mt-1 pl-[12.75rem] text-xs text-loss">{errors[field.key]}</p>
              )}
            </li>
          );
        })}
      </ul>
      <p
        role="status"
        className={clsx(
          'num mt-4 flex items-center justify-between rounded-lg px-3 py-2 text-sm font-medium',
          ok ? 'bg-brand-soft text-brand-dark' : 'bg-loss-soft text-loss',
        )}
      >
        <span>Total</span>
        <span>
          {total} / {WEIGHTS_TOTAL}
          {!ok && <span className="ml-2 font-normal">must add up to {WEIGHTS_TOTAL}</span>}
        </span>
      </p>
    </div>
  );
}
