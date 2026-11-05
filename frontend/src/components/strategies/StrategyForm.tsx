// Create or edit one strategy (a profile in the API). The parameter sections are generated from the ParamSpec; the backend has the final say on validation.
import { RotateCcw } from 'lucide-react';
import { useMemo, useState, type FormEvent } from 'react';
import { errorMessage } from '../../api/client';
import { useCreateProfile, useUpdateProfile } from '../../hooks/useProfiles';
import type { ParamSpec, Profile } from '../../types/api';
import { Button } from '../ui/Button';
import { Card } from '../ui/Card';
import { Field } from '../ui/Field';
import { Input } from '../ui/Input';
import { useToast } from '../ui/Toast';
import {
  WEIGHTS_TOTAL,
  buildDraft,
  draftToParams,
  isSameDraft,
  validateDraft,
  weightsTotal,
  type Draft,
  type DraftValue,
} from './paramDraft';
import { ParamSection } from './ParamSection';

export function StrategyForm({
  spec,
  profile,
  onSaved,
}: {
  spec: ParamSpec;
  profile: Profile | null;
  onSaved: (p: Profile) => void;
}) {
  const toast = useToast();
  const create = useCreateProfile();
  const update = useUpdateProfile();
  const mutation = profile ? update : create;

  const initial = useMemo(() => buildDraft(spec, profile?.params), [spec, profile]);
  const [name, setName] = useState(profile?.name ?? '');
  const [draft, setDraft] = useState<Draft>(initial);
  const [touched, setTouched] = useState(false);
  // Changing this remounts the inputs, so number boxes pick up values set by "Reset".
  const [resetCount, setResetCount] = useState(0);

  const errors = validateDraft(spec, draft);
  const total = weightsTotal(spec, draft);
  const weightsOk = total === WEIGHTS_TOTAL;
  const nameOk = name.trim().length > 0;
  const paramsValid = Object.keys(errors).length === 0 && weightsOk;
  const dirty = profile ? name.trim() !== profile.name || !isSameDraft(draft, initial) : true;

  const setValue = (key: string, value: DraftValue) => {
    mutation.reset();
    setDraft((d) => ({ ...d, [key]: value }));
  };
  const resetTo = (next: Draft) => {
    mutation.reset();
    setDraft(next);
    setResetCount((c) => c + 1);
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setTouched(true);
    if (!nameOk || !paramsValid) return;
    const params = draftToParams(spec, draft);
    try {
      const saved = profile
        ? await update.mutateAsync({
            id: profile.id,
            body: { name: name.trim(), params },
          })
        : await create.mutateAsync({ name: name.trim(), params });
      toast.success(profile ? `Saved ${saved.name}` : `Created ${saved.name}`);
      onSaved(saved);
    } catch {
      /* the backend's message is shown under the form via mutation.error */
    }
  };

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-4">
      <Card title={profile ? 'Strategy' : 'New strategy'}>
        <div className="max-w-xl">
          <Field label="Strategy name" error={touched && !nameOk ? 'A name is required' : null}>
            {(props) => (
              <Input
                {...props}
                value={name}
                onChange={(e) => {
                  mutation.reset();
                  setName(e.target.value);
                }}
                placeholder="e.g. Early Setups, Large Cap Steady"
                className="w-full"
              />
            )}
          </Field>
        </div>
      </Card>

      <div key={resetCount} className="space-y-4">
        {spec.sections.map((section) => (
          <ParamSection
            key={section.section}
            spec={spec}
            section={section}
            draft={draft}
            errors={errors}
            onChange={setValue}
          />
        ))}
      </div>

      <div className="sticky bottom-0 -mx-1 rounded-lg border border-line bg-white/95 p-3 shadow-sm backdrop-blur">
        {mutation.error && (
          <p role="alert" className="mb-3 rounded-lg bg-loss-soft px-3 py-2 text-sm text-loss">
            {errorMessage(mutation.error)}
          </p>
        )}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="text-xs text-ink-muted">
            {!weightsOk ? (
              <span className="text-loss">
                Scoring weights add up to {total}; they must total {WEIGHTS_TOTAL}.
              </span>
            ) : !paramsValid ? (
              <span className="text-loss">Fix the highlighted fields to save.</span>
            ) : profile && !dirty ? (
              'No unsaved changes.'
            ) : (
              'Changes apply to the next algo run.'
            )}
          </div>
          <div className="flex gap-2">
            <Button variant="ghost" onClick={() => resetTo(buildDraft(spec, undefined))}>
              <RotateCcw className="h-4 w-4" aria-hidden /> Defaults
            </Button>
            {profile && (
              <Button
                variant="secondary"
                disabled={!dirty}
                onClick={() => {
                  setName(profile.name);
                  resetTo(initial);
                }}
              >
                Discard changes
              </Button>
            )}
            <Button
              type="submit"
              loading={mutation.isPending}
              disabled={(profile ? !dirty : false) || !paramsValid}
            >
              {profile ? 'Save changes' : 'Create strategy'}
            </Button>
          </div>
        </div>
      </div>
    </form>
  );
}
