// White rounded panel with an optional title row.
import clsx from 'clsx';
import type { ReactNode } from 'react';

export function Card({
  title,
  right,
  className,
  children,
}: {
  title?: ReactNode;
  right?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section className={clsx('rounded-lg border border-line bg-white', className)}>
      {(title || right) && (
        <header className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
          <h3 className="text-sm font-semibold text-ink">{title}</h3>
          {right}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}
