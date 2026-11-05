// Strategies: manage strategies (named sets of screening parameters; "profiles" in the API). The edit form is built from GET /profiles/param-spec.
import { Settings2 } from 'lucide-react';
import { useState } from 'react';
import { StrategyForm } from '../components/strategies/StrategyForm';
import { StrategyList } from '../components/strategies/StrategyList';
import { PageHeader } from '../components/layout/PageHeader';
import { ErrorNotice } from '../components/ui/ErrorNotice';
import { Skeleton } from '../components/ui/Skeleton';
import { useToast } from '../components/ui/Toast';
import { useParamSpec } from '../hooks/useProfiles';
import { useActiveProfile } from '../store/activeProfile';
import type { Profile } from '../types/api';

export default function StrategiesPage() {
  const toast = useToast();
  const { profile: active, profiles, isLoading, selectProfile } = useActiveProfile();
  const specQuery = useParamSpec();
  const [selected, setSelected] = useState<number | 'new' | null>(null);

  // Show what was picked, else the active strategy; if the pick no longer exists (deleted), fall back too.
  const shownId: number | 'new' | null =
    selected === 'new'
      ? 'new'
      : profiles.some((p) => p.id === selected)
        ? selected
        : (active?.id ?? null);
  const shown: Profile | null =
    typeof shownId === 'number' ? (profiles.find((p) => p.id === shownId) ?? null) : null;

  const activate = (p: Profile) => {
    selectProfile(p.id);
    toast.success(`${p.name} is now the active strategy`);
  };

  if (isLoading) return <Skeleton className="h-64 w-full" />;

  return (
    <div className="space-y-4">
      <PageHeader
        title="Strategies"
        description="A strategy is a named set of screening parameters. The active strategy drives Stocks, Tracker and Loss Analysis."
      />
      <div className="grid items-start gap-6 lg:grid-cols-[320px_minmax(0,1fr)]">
        <StrategyList
          profiles={profiles}
          selected={shownId}
          activeId={active?.id ?? null}
          onSelect={setSelected}
          onNew={() => setSelected('new')}
          onActivate={activate}
          onDeleted={(id) => selected === id && setSelected(null)}
        />
        <div className="min-w-0">
          {specQuery.error ? (
            <ErrorNotice error={specQuery.error} onRetry={() => void specQuery.refetch()} />
          ) : !specQuery.data ? (
            <div className="space-y-4">
              <Skeleton className="h-28" />
              <Skeleton className="h-48" />
              <Skeleton className="h-48" />
            </div>
          ) : shownId === 'new' || shown ? (
            <StrategyForm
              key={shown ? `${shown.id}-${shown.updated_at}` : 'new'}
              spec={specQuery.data}
              profile={shown}
              onSaved={(saved) => setSelected(saved.id)}
            />
          ) : (
            <div className="flex flex-col items-center rounded-lg border border-dashed border-line bg-white px-6 py-12 text-center">
              <Settings2 className="mb-3 h-6 w-6 text-ink-muted" aria-hidden />
              <p className="text-sm text-ink-muted">
                No strategy yet. Create one with “New strategy”.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
