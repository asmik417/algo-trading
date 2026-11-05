// One input for one ParamField, chosen by the field's `type` from the spec (number / int / bool / select / multiselect).
import clsx from 'clsx';
import { useId, useState } from 'react';
import type { ParamField, ParamSpec } from '../../types/api';
import { ChipGroup } from '../ui/ChipGroup';
import { Input, Select } from '../ui/Input';
import { optionsFor, type DraftValue } from './paramDraft';

interface Props {
  spec: ParamSpec;
  field: ParamField;
  value: DraftValue;
  error: string | null;
  onChange: (value: DraftValue) => void;
  /** Compact = no label or help text (used inside the weights editor, which shows its own label). */
  bare?: boolean;
}

const rangeHint = (f: ParamField): string | null =>
  f.min !== undefined && f.max !== undefined ? `Allowed range ${f.min} to ${f.max}` : null;

/** A number box that keeps what the user typed, and reports null while the text is not a number. */
export function NumberBox({
  id,
  field,
  value,
  onChange,
  invalid,
  className,
}: {
  id: string;
  field: ParamField;
  value: DraftValue;
  onChange: (value: DraftValue) => void;
  invalid: boolean;
  className?: string;
}) {
  const [text, setText] = useState(typeof value === 'number' ? String(value) : '');
  return (
    <Input
      id={id}
      type="number"
      inputMode="decimal"
      min={field.min}
      max={field.max}
      step={field.step ?? (field.type === 'int' ? 1 : 'any')}
      value={text}
      aria-invalid={invalid || undefined}
      className={clsx(
        'num',
        invalid && 'border-loss focus:border-loss focus:ring-loss/20',
        className,
      )}
      onChange={(e) => {
        setText(e.target.value);
        const n = e.target.value.trim() === '' ? Number.NaN : Number(e.target.value);
        onChange(Number.isFinite(n) ? n : null);
      }}
    />
  );
}

function Switch({
  id,
  checked,
  onChange,
  labelledBy,
}: {
  id: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  labelledBy: string;
}) {
  return (
    <button
      id={id}
      type="button"
      role="switch"
      aria-checked={checked}
      aria-labelledby={labelledBy}
      onClick={() => onChange(!checked)}
      className={clsx(
        'relative h-6 w-11 shrink-0 rounded-full transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand/40',
        checked ? 'bg-brand' : 'bg-slate-300',
      )}
    >
      <span
        className={clsx(
          'absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform',
          checked && 'translate-x-5',
        )}
      />
    </button>
  );
}

export function ParamFieldControl({ spec, field, value, error, onChange, bare = false }: Props) {
  const id = useId();
  const labelId = `${id}-label`;
  const messageId = `${id}-message`;
  const hint = [field.help, rangeHint(field)].filter(Boolean).join(' · ');

  const message = error ? (
    <p id={messageId} className="mt-1 text-xs text-loss">
      {error}
    </p>
  ) : hint && !bare ? (
    <p id={messageId} className="mt-1 text-xs text-ink-muted">
      {hint}
    </p>
  ) : null;

  if (field.type === 'bool') {
    return (
      <div>
        <div className="flex items-center justify-between gap-4">
          <span id={labelId} className="text-sm font-medium text-ink">
            {field.label}
          </span>
          <Switch id={id} checked={value === true} onChange={onChange} labelledBy={labelId} />
        </div>
        {message}
      </div>
    );
  }

  let control;
  if (field.type === 'number' || field.type === 'int') {
    control = (
      <NumberBox
        id={id}
        field={field}
        value={value}
        onChange={onChange}
        invalid={!!error}
        className="w-full"
      />
    );
  } else if (field.type === 'select') {
    control = (
      <Select
        id={id}
        value={typeof value === 'string' ? value : ''}
        onChange={(e) => onChange(e.target.value)}
        className="w-full"
        aria-invalid={!!error || undefined}
      >
        {optionsFor(spec, field).map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </Select>
    );
  } else {
    control = (
      <ChipGroup
        label={field.label}
        options={optionsFor(spec, field).map((o) => ({ value: o, label: o }))}
        selected={Array.isArray(value) ? value : []}
        onChange={onChange}
      />
    );
  }

  return (
    <div>
      {!bare &&
        (field.type === 'multiselect' ? (
          <div id={labelId} className="mb-1.5 block text-sm font-medium text-ink">
            {field.label}
          </div>
        ) : (
          <label htmlFor={id} className="mb-1 block text-sm font-medium text-ink">
            {field.label}
          </label>
        ))}
      {control}
      {message}
    </div>
  );
}
