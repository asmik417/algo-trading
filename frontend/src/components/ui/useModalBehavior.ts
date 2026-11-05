// Shared behaviour for Dialog and Drawer: Escape closes only the top-most modal, Tab stays inside it,
// the page behind does not scroll, and focus returns to whatever opened it.
import { useEffect, useRef, type RefObject } from 'react';

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])';
const openModals: symbol[] = [];

export function useModalBehavior(
  open: boolean,
  onClose: () => void,
  panelRef: RefObject<HTMLElement>,
): void {
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  });

  useEffect(() => {
    if (!open) return;
    const token = Symbol('modal');
    openModals.push(token);
    const opener = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    panelRef.current?.focus();

    const onKey = (e: KeyboardEvent) => {
      if (openModals[openModals.length - 1] !== token) return; // a modal opened on top of this one handles keys
      const panel = panelRef.current;
      if (e.key === 'Escape') {
        e.preventDefault();
        onCloseRef.current();
      } else if (e.key === 'Tab' && panel) {
        const items = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE));
        if (items.length === 0) return;
        const first = items[0];
        const last = items[items.length - 1];
        if (e.shiftKey && (document.activeElement === first || document.activeElement === panel)) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      openModals.splice(openModals.indexOf(token), 1);
      if (openModals.length === 0) document.body.style.overflow = previousOverflow;
      opener?.focus?.();
    };
  }, [open, panelRef]);
}
