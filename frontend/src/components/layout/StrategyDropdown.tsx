// "Active strategy": shows the strategy every page works under, lets you switch it, or jump to Strategies to manage them.
import clsx from 'clsx';
import { Check, ChevronsUpDown, Settings2, SlidersHorizontal } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useActiveProfile } from '../../store/activeProfile';
import { Skeleton } from '../ui/Skeleton';
import { useToast } from '../ui/Toast';

export function StrategyDropdown() {
  const { profile, profiles, isLoading, selectProfile } = useActiveProfile();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: PointerEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
    document.addEventListener('pointerdown', onPointerDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('pointerdown', onPointerDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  if (isLoading) return <Skeleton className="mx-3 my-3 h-14 lg:mx-4" />;

  return (
    <div ref={rootRef} className="relative px-3 py-3 lg:px-4">
      <div className="mb-1 hidden text-[11px] font-medium uppercase tracking-wide text-ink-muted lg:block">
        Active strategy
      </div>
      <button
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={`Active strategy: ${profile?.name ?? 'none'}`}
        title={profile ? `Active strategy: ${profile.name}` : 'No strategy yet'}
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-3 rounded-lg border border-line bg-white p-0.5 text-left transition hover:border-brand focus:outline-none focus-visible:ring-2 focus-visible:ring-brand/40 lg:p-2"
      >
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-soft text-brand-dark lg:h-9 lg:w-9">
          <SlidersHorizontal className="h-4 w-4" aria-hidden />
        </span>
        <span className="hidden min-w-0 flex-1 lg:block">
          <span className="block truncate text-sm font-medium text-ink">
            {profile?.name ?? 'No strategy yet'}
          </span>
          {!profile && (
            <span className="block truncate text-xs text-ink-muted">Create one in Strategies</span>
          )}
        </span>
        <ChevronsUpDown className="hidden h-4 w-4 shrink-0 text-ink-faint lg:block" aria-hidden />
      </button>

      {open && (
        <div
          role="listbox"
          aria-label="Choose strategy"
          className="absolute left-3 top-full z-30 -mt-1 w-64 rounded-lg border border-line bg-white p-1 shadow-lg lg:left-4 lg:w-[calc(100%-2rem)]"
        >
          {profiles.length === 0 && (
            <p className="px-3 py-2 text-sm text-ink-muted">No strategies yet.</p>
          )}
          {profiles.map((p) => {
            const selected = p.id === profile?.id;
            return (
              <button
                key={p.id}
                role="option"
                aria-selected={selected}
                type="button"
                onClick={() => {
                  if (!selected) {
                    selectProfile(p.id);
                    toast.success(`Switched to ${p.name}`);
                  }
                  setOpen(false);
                }}
                className={clsx(
                  'flex w-full items-center gap-2 rounded-md px-3 py-2 text-left hover:bg-slate-50',
                  selected && 'bg-brand-soft/60',
                )}
              >
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-ink">{p.name}</span>
                  <span className="block truncate text-xs text-ink-muted" title={p.params_summary}>
                    {p.params_summary}
                  </span>
                </span>
                {selected && <Check className="h-4 w-4 shrink-0 text-brand" aria-hidden />}
              </button>
            );
          })}
          <div className="my-1 border-t border-line" />
          <Link
            to="/strategies"
            onClick={() => setOpen(false)}
            className="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-ink-muted hover:bg-slate-50 hover:text-ink"
          >
            <Settings2 className="h-4 w-4" aria-hidden /> Manage strategies
          </Link>
        </div>
      )}
    </div>
  );
}
