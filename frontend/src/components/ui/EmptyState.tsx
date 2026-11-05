// Friendly "nothing here yet" block with an optional action.
import type { LucideIcon } from 'lucide-react';
import type { ReactNode } from 'react';

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon?: LucideIcon;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center rounded-lg border border-dashed border-line bg-white px-6 py-12 text-center">
      {Icon && (
        <span className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-slate-100 text-ink-muted">
          <Icon className="h-5 w-5" aria-hidden />
        </span>
      )}
      <h3 className="text-sm font-semibold text-ink">{title}</h3>
      {description && <p className="mt-1 max-w-md text-sm text-ink-muted">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
