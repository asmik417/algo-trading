// Centered modal dialog. Escape or a click on the backdrop closes it.
import clsx from 'clsx';
import { X } from 'lucide-react';
import { useRef, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { useModalBehavior } from './useModalBehavior';

interface Props {
  open: boolean;
  onClose: () => void;
  /** Accessible name; also shown as the title unless `hideTitle`. */
  title: string;
  hideTitle?: boolean;
  maxWidth?: string;
  children: ReactNode;
}

export function Dialog({
  open,
  onClose,
  title,
  hideTitle = false,
  maxWidth = 'max-w-[1100px]',
  children,
}: Props) {
  const panelRef = useRef<HTMLDivElement>(null);
  useModalBehavior(open, onClose, panelRef);

  if (!open) return null;
  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/40 p-4 sm:p-8"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        className={clsx('relative w-full rounded-lg bg-white shadow-xl outline-none', maxWidth)}
      >
        {!hideTitle && (
          <header className="flex items-center justify-between border-b border-line px-5 py-3 pr-14">
            <h2 className="text-base font-semibold text-ink">{title}</h2>
          </header>
        )}
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="absolute right-3 top-3 rounded-lg p-1.5 text-ink-muted hover:bg-slate-100 hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-brand/40"
        >
          <X className="h-5 w-5" aria-hidden />
        </button>
        {children}
      </div>
    </div>,
    document.body,
  );
}
