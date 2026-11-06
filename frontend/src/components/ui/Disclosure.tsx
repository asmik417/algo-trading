// A collapsible row: a button that shows or hides its content (collapsed by default).
import clsx from 'clsx';
import { ChevronRight } from 'lucide-react';
import { useId, useState, type ReactNode } from 'react';

export function Disclosure({
  title,
  aside,
  defaultOpen = false,
  className,
  children,
}: {
  title: ReactNode;
  /** Shown at the right of the title row (e.g. "6/9"). */
  aside?: ReactNode;
  defaultOpen?: boolean;
  className?: string;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const id = useId();
  return (
    <div className={className}>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 rounded-lg py-2 text-left text-sm font-medium text-ink hover:text-brand-dark focus:outline-none focus-visible:ring-2 focus-visible:ring-brand/40"
      >
        <ChevronRight
          className={clsx(
            'h-4 w-4 shrink-0 text-ink-muted transition-transform',
            open && 'rotate-90',
          )}
          aria-hidden
        />
        <span className="flex-1">{title}</span>
        {aside}
      </button>
      {open && (
        <div id={id} className="pb-3 pl-6">
          {children}
        </div>
      )}
    </div>
  );
}
