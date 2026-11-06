// The pick-list header in My Picks: list dropdown (by name, plus "New list…"), the list name with inline rename,
// and a confirmed Delete. A new list gets a name box instead (default "List <n>").
import { Check, Pencil, Trash2, X } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { errorMessage } from '../../api/client';
import { useDeletePickList, useUpdatePickList } from '../../hooks/usePickLists';
import type { PickList } from '../../types/api';
import { Button } from '../ui/Button';
import { Dialog } from '../ui/Dialog';
import { Input, Select } from '../ui/Input';
import { useToast } from '../ui/Toast';

export const MAX_LIST_NAME = 60;
export const NEW_LIST = 'new';

interface Props {
  lists: PickList[];
  selected: PickList | null;
  /** Name typed for a list that does not exist yet (only when `selected` is null). */
  newName: string;
  onNewNameChange: (name: string) => void;
  onSelect: (id: number | typeof NEW_LIST) => void;
  onDeleted: () => void;
  disabled?: boolean;
}

function RenameForm({ list, onDone }: { list: PickList; onDone: () => void }) {
  const toast = useToast();
  const update = useUpdatePickList();
  const [name, setName] = useState(list.name);
  const trimmed = name.trim();
  const valid = trimmed.length > 0 && trimmed.length <= MAX_LIST_NAME;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!valid) return;
    if (trimmed === list.name) return onDone();
    try {
      await update.mutateAsync({ id: list.id, body: { name: trimmed } });
      toast.success(`Renamed to ${trimmed}`);
      onDone();
    } catch {
      /* shown below via update.error */
    }
  };

  return (
    <form onSubmit={onSubmit} className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
      <Input
        autoFocus
        aria-label="List name"
        value={name}
        maxLength={MAX_LIST_NAME}
        onChange={(e) => {
          update.reset();
          setName(e.target.value);
        }}
        onKeyDown={(e) => e.key === 'Escape' && onDone()}
        className="w-64"
      />
      <Button
        type="submit"
        size="sm"
        loading={update.isPending}
        disabled={!valid}
        aria-label="Save name"
      >
        {!update.isPending && <Check className="h-4 w-4" aria-hidden />}
        Save
      </Button>
      <Button size="sm" variant="ghost" onClick={onDone} aria-label="Cancel rename">
        <X className="h-4 w-4" aria-hidden />
      </Button>
      {update.error && (
        <p role="alert" className="w-full text-xs text-loss">
          {errorMessage(update.error)}
        </p>
      )}
    </form>
  );
}

export function PickListBar({
  lists,
  selected,
  newName,
  onNewNameChange,
  onSelect,
  onDeleted,
  disabled = false,
}: Props) {
  const toast = useToast();
  const remove = useDeletePickList();
  const [renaming, setRenaming] = useState(false);
  const [confirming, setConfirming] = useState(false);

  const confirmDelete = async () => {
    if (!selected) return;
    try {
      await remove.mutateAsync(selected.id);
      toast.success(`Deleted ${selected.name}`);
      setConfirming(false);
      onDeleted();
    } catch (e) {
      toast.error(errorMessage(e));
      setConfirming(false);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-3">
      <Select
        aria-label="Pick list"
        value={selected ? String(selected.id) : NEW_LIST}
        disabled={disabled}
        onChange={(e) => {
          setRenaming(false);
          onSelect(e.target.value === NEW_LIST ? NEW_LIST : Number(e.target.value));
        }}
        className="w-56"
      >
        {lists.map((l) => (
          <option key={l.id} value={l.id}>
            {l.name}
          </option>
        ))}
        <option value={NEW_LIST}>New list…</option>
      </Select>

      {selected ? (
        renaming ? (
          <RenameForm key={selected.id} list={selected} onDone={() => setRenaming(false)} />
        ) : (
          <div className="flex min-w-0 flex-1 items-center gap-1">
            <h3 className="truncate text-sm font-semibold text-ink" title={selected.name}>
              {selected.name}
            </h3>
            <button
              type="button"
              onClick={() => setRenaming(true)}
              disabled={disabled}
              aria-label="Rename list"
              title="Rename list"
              className="rounded p-1 text-ink-muted hover:bg-slate-100 hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-brand/40"
            >
              <Pencil className="h-3.5 w-3.5" aria-hidden />
            </button>
            <span className="num ml-1 text-xs text-ink-muted">
              {selected.symbols.length} stock{selected.symbols.length === 1 ? '' : 's'}
            </span>
          </div>
        )
      ) : (
        <label className="flex min-w-0 flex-1 items-center gap-2 text-sm text-ink-muted">
          Name
          <Input
            aria-label="New list name"
            value={newName}
            maxLength={MAX_LIST_NAME}
            onChange={(e) => onNewNameChange(e.target.value)}
            className="w-64"
          />
        </label>
      )}

      {selected && !renaming && (
        <Button
          size="sm"
          variant="ghost"
          onClick={() => setConfirming(true)}
          disabled={disabled}
          className="text-loss hover:text-loss"
        >
          <Trash2 className="h-4 w-4" aria-hidden /> Delete list
        </Button>
      )}

      <Dialog
        open={confirming && !!selected}
        onClose={() => setConfirming(false)}
        title="Delete pick list?"
        maxWidth="max-w-md"
      >
        {selected && (
          <div className="space-y-4 px-5 pb-5 pt-4">
            <p className="text-sm text-ink">
              Delete <strong>{selected.name}</strong> ({selected.symbols.length} stocks)? Past
              analyses of it are kept.
            </p>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setConfirming(false)}>
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
