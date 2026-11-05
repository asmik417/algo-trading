// Right-hand slide-over panel (position details). Escape or a click on the backdrop closes it.
import { X } from 'lucide-react';
import { useRef, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { useModalBehavior } from './useModalBehavior';

export function Drawer({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}) {
  const panelRef = useRef<HTMLElement>(null);
  useModalBehavior(open, onClose, panelRef);

  if (!open) return null;
  return createPortal(
    <div
      className="fixed inset-0 z-40 bg-slate-900/40"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <aside
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        className="absolute right-0 top-0 flex h-full w-full max-w-[540px] flex-col overflow-y-auto bg-white shadow-xl outline-none"
      >
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="absolute right-3 top-3 z-10 rounded-lg p-1.5 text-ink-muted hover:bg-slate-100 hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-brand/40"
        >
          <X className="h-5 w-5" aria-hidden />
        </button>
        {children}
      </aside>
    </div>,
    document.body,
  );
}
