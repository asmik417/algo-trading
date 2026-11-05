// One card per spec section, with the section's help text. The scoring-weights section gets its own editor.
import type { ParamSection as ParamSectionSpec, ParamSpec } from '../../types/api';
import { Card } from '../ui/Card';
import { ParamFieldControl } from './ParamFieldControl';
import { WEIGHTS_SECTION, type Draft, type DraftValue } from './paramDraft';
import { WeightsEditor } from './WeightsEditor';

export function ParamSection({
  spec,
  section,
  draft,
  errors,
  onChange,
}: {
  spec: ParamSpec;
  section: ParamSectionSpec;
  draft: Draft;
  errors: Record<string, string>;
  onChange: (key: string, value: DraftValue) => void;
}) {
  return (
    <Card title={section.section}>
      {section.help && <p className="-mt-1 mb-4 text-sm text-ink-muted">{section.help}</p>}
      {section.section === WEIGHTS_SECTION ? (
        <WeightsEditor
          spec={spec}
          section={section}
          draft={draft}
          errors={errors}
          onChange={onChange}
        />
      ) : (
        <div className="grid gap-x-6 gap-y-4 md:grid-cols-2">
          {section.fields.map((field) => (
            <div
              key={field.key}
              className={field.type === 'multiselect' ? 'md:col-span-2' : undefined}
            >
              <ParamFieldControl
                spec={spec}
                field={field}
                value={draft[field.key] ?? null}
                error={errors[field.key] ?? null}
                onChange={(v) => onChange(field.key, v)}
              />
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
