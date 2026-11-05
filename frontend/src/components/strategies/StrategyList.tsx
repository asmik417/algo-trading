// Left column of the Strategies page: every strategy as a card, with New / Activate / Delete.
import clsx from 'clsx';
import { Plus, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { errorMessage } from '../../api/client';
import { useDeleteProfile } from '../../hooks/useProfiles';
import type { Profile } from '../../types/api';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { Dialog } from '../ui/Dialog';
import { useToast } from '../ui/Toast';

interface Props {
  profiles: Profile[];
  /** The strategy shown in the form on the right, or 'new'. */
  selected: number | 'new' | null;
  /** The strategy the whole app currently works as. */
  activeId: number | null;
  onSelect: (id: number) => void;
  onNew: () => void;
  onActivate: (p: Profile) => void;
  onDeleted: (id: number) => void;
}

export function StrategyList({
  profiles,
  selected,
  activeId,
  onSelect,
  onNew,
  onActivate,
  onDeleted,
}: Props) {
  const toast = useToast();
  const remove = useDeleteProfile();
  const [toDelete, setToDelete] = useState<Profile | null>(null);

  const confirmDelete = async () => {
    if (!toDelete) return;
    try {
      await remove.mutateAsync(toDelete.id);
      toast.success(`Deleted ${toDelete.name}`);
      onDeleted(toDelete.id);
      setToDelete(null);
    } catch (e) {
      toast.error(errorMessage(e));
      setToDelete(null);
    }
  };

  return (
    <div className="space-y-3">
      <Button
        className="w-full"
        onClick={onNew}
        variant={selected === 'new' ? 'secondary' : 'primary'}
      >
        <Plus className="h-4 w-4" aria-hidden /> New strategy
      </Button>
      <ul className="space-y-2" aria-label="Strategies">
        {profiles.map((p) => {
          const isActive = p.id === activeId;
          const isSelected = p.id === selected;
          return (
            <li key={p.id}>
              <div
                className={clsx(
                  'rounded-lg border bg-white p-3 transition',
                  isSelected
                    ? 'border-brand ring-1 ring-brand/30'
                    : 'border-line hover:border-slate-300',
                )}
              >
                <button
                  type="button"
                  onClick={() => onSelect(p.id)}
                  aria-current={isSelected}
                  className="block w-full text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-brand/40"
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-semibold text-ink">
                        {p.name}
                      </span>
                    </span>
                    {isActive && <Badge tone="green">Active</Badge>}
                  </div>
                  <p className="mt-2 text-xs leading-relaxed text-ink-muted">{p.params_summary}</p>
                </button>
                <div className="mt-3 flex items-center justify-between">
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={isActive}
                    onClick={() => onActivate(p)}
                  >
                    {isActive ? 'Active' : 'Activate'}
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setToDelete(p)}
                    aria-label={`Delete ${p.name}`}
                  >
                    <Trash2 className="h-4 w-4" aria-hidden />
                  </Button>
                </div>
              </div>
            </li>
          );
        })}
      </ul>

      <Dialog
        open={toDelete !== null}
        onClose={() => setToDelete(null)}
        title="Delete strategy?"
        maxWidth="max-w-md"
      >
        {toDelete && (
          <div className="space-y-4 px-5 pb-5 pt-4">
            <p className="text-sm text-ink">
              Delete <strong>{toDelete.name}</strong>? This cannot be undone.
              {toDelete.id === activeId &&
                ' It is the active strategy, so the app will switch to another one.'}
            </p>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setToDelete(null)}>
                Cancel
              </Button>
              <Button
                variant="danger"
                loading={remove.isPending}
                onClick={() => void confirmDelete()}
              >
                Delete
              </Button>
            </div>
          </div>
        )}
      </Dialog>
    </div>
  );
}
