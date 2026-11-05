// Small auto-dismissing messages in the bottom-right corner. Use: const toast = useToast(); toast.success('Saved').
import clsx from 'clsx';
import { CheckCircle2, Info, XCircle } from 'lucide-react';
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';

type Kind = 'success' | 'error' | 'info';
interface ToastItem {
  id: number;
  kind: Kind;
  message: string;
}
interface ToastApi {
  success: (message: string) => void;
  error: (message: string) => void;
  info: (message: string) => void;
}

const ToastContext = createContext<ToastApi | null>(null);
const LIFETIME_MS = 4500;
let nextId = 1;

const ICONS = { success: CheckCircle2, error: XCircle, info: Info } as const;
const STYLES: Record<Kind, string> = {
  success: 'border-brand/30 text-brand-dark',
  error: 'border-loss/30 text-loss',
  info: 'border-line text-ink',
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);

  const push = useCallback((kind: Kind, message: string) => {
    const id = nextId++;
    setItems((cur) => [...cur.slice(-3), { id, kind, message }]);
    setTimeout(() => setItems((cur) => cur.filter((t) => t.id !== id)), LIFETIME_MS);
  }, []);

  const api = useMemo<ToastApi>(
    () => ({
      success: (m) => push('success', m),
      error: (m) => push('error', m),
      info: (m) => push('info', m),
    }),
    [push],
  );

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-80 flex-col gap-2"
      >
        {items.map((t) => {
          const Icon = ICONS[t.kind];
          return (
            <div
              key={t.id}
              className={clsx(
                'pointer-events-auto flex items-start gap-2 rounded-lg border bg-white p-3 text-sm shadow-lg',
                STYLES[t.kind],
              )}
            >
              <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
              <span className="text-ink">{t.message}</span>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used inside <ToastProvider>');
  return ctx;
}
