// Editing state for the profile form. Everything is driven by the ParamSpec: no parameter name is hard-coded here
// except the section title the contract reserves for the scoring weights.
import type { ParamField, ParamSpec, Params } from '../../types/api';

/** null = a number box whose text is not a valid number (yet). */
export type DraftValue = number | boolean | string | string[] | null;
export type Draft = Record<string, DraftValue>;

/** The contract names this section exactly; its fields are `int` and must total 100. */
export const WEIGHTS_SECTION = 'Scoring weights';
export const WEIGHTS_TOTAL = 100;

export const allFields = (spec: ParamSpec): ParamField[] => spec.sections.flatMap((s) => s.fields);

/** Options for select / multiselect fields: the field's own list, else the spec-level list for that type. */
export function optionsFor(spec: ParamSpec, field: ParamField): string[] {
  if (field.options && field.options.length > 0) return field.options;
  return field.type === 'multiselect'
    ? spec.cap_buckets
    : field.type === 'select'
      ? spec.horizons
      : [];
}

function coerce(field: ParamField, raw: unknown): DraftValue {
  switch (field.type) {
    case 'number':
    case 'int': {
      const n = typeof raw === 'number' ? raw : Number(raw);
      return raw === null || raw === undefined || raw === '' || !Number.isFinite(n) ? null : n;
    }
    case 'bool':
      return Boolean(raw);
    case 'select':
      return typeof raw === 'string' ? raw : '';
    case 'multiselect':
      return Array.isArray(raw) ? raw.map(String) : [];
  }
}

/** Saved values win; anything the profile does not have yet falls back to the spec's default. */
export function buildDraft(spec: ParamSpec, params: Params | undefined): Draft {
  const draft: Draft = {};
  for (const field of allFields(spec)) {
    draft[field.key] = coerce(field, params?.[field.key] ?? spec.defaults[field.key]);
  }
  return draft;
}

export function validateField(
  spec: ParamSpec,
  field: ParamField,
  value: DraftValue,
): string | null {
  switch (field.type) {
    case 'number':
    case 'int': {
      if (typeof value !== 'number') return 'Enter a number';
      if (field.type === 'int' && !Number.isInteger(value)) return 'Enter a whole number';
      if (field.min !== undefined && value < field.min) return `Must be at least ${field.min}`;
      if (field.max !== undefined && value > field.max) return `Must be at most ${field.max}`;
      return null;
    }
    case 'select': {
      const options = optionsFor(spec, field);
      return typeof value === 'string' && (options.length === 0 || options.includes(value))
        ? null
        : 'Choose an option';
    }
    case 'multiselect':
      return Array.isArray(value) && value.length > 0 ? null : 'Pick at least one';
    case 'bool':
      return null;
  }
}

export function validateDraft(spec: ParamSpec, draft: Draft): Record<string, string> {
  const errors: Record<string, string> = {};
  for (const field of allFields(spec)) {
    const message = validateField(spec, field, draft[field.key] ?? null);
    if (message) errors[field.key] = message;
  }
  return errors;
}

export function weightKeys(spec: ParamSpec): string[] {
  return spec.sections.find((s) => s.section === WEIGHTS_SECTION)?.fields.map((f) => f.key) ?? [];
}

export function weightsTotal(spec: ParamSpec, draft: Draft): number {
  return weightKeys(spec).reduce((sum, key) => {
    const v = draft[key];
    return sum + (typeof v === 'number' ? v : 0);
  }, 0);
}

/** Only valid drafts are converted; keys come from the spec, so unknown keys can never be sent. */
export function draftToParams(spec: ParamSpec, draft: Draft): Params {
  const params: Params = {};
  for (const field of allFields(spec)) {
    const v = draft[field.key];
    if (v !== null && v !== undefined) params[field.key] = v;
  }
  return params;
}

const canonical = (draft: Draft): string =>
  JSON.stringify(
    Object.keys(draft)
      .sort()
      .map((k) => [k, Array.isArray(draft[k]) ? [...(draft[k] as string[])].sort() : draft[k]]),
  );

export const isSameDraft = (a: Draft, b: Draft): boolean => canonical(a) === canonical(b);
