// Dense table primitives: sticky header, right-aligned tabular numbers, optional sticky action column.
import clsx from 'clsx';
import type { ReactNode } from 'react';

type Align = 'left' | 'right' | 'center';
const ALIGN: Record<Align, string> = {
  left: 'text-left',
  right: 'text-right num',
  center: 'text-center',
};

export function TableWrap({
  children,
  maxHeight = 'max-h-[calc(100vh-17rem)]',
  className,
}: {
  children: ReactNode;
  maxHeight?: string;
  className?: string;
}) {
  return (
    <div
      className={clsx('overflow-auto rounded-lg border border-line bg-white', maxHeight, className)}
    >
      {children}
    </div>
  );
}

export function Table({ children }: { children: ReactNode }) {
  return <table className="min-w-full border-separate border-spacing-0 text-sm">{children}</table>;
}

interface CellProps {
  align?: Align;
  className?: string;
  /** Keeps the column visible while the table scrolls sideways (the action column). Rows need the `group` class. */
  stickyRight?: boolean;
  colSpan?: number;
  children?: ReactNode;
}

export function Th({ align = 'left', className, stickyRight = false, children }: CellProps) {
  return (
    <th
      scope="col"
      className={clsx(
        'sticky top-0 z-[1] whitespace-nowrap border-b border-line bg-slate-50 px-3 py-2 text-xs font-medium uppercase tracking-wide text-ink-muted',
        ALIGN[align],
        stickyRight && 'right-0 !z-[2] border-l',
        className,
      )}
    >
      {children}
    </th>
  );
}

export function Td({
  align = 'left',
  className,
  stickyRight = false,
  colSpan,
  children,
}: CellProps) {
  return (
    <td
      colSpan={colSpan}
      className={clsx(
        'whitespace-nowrap border-b border-line/70 px-3 py-2.5',
        ALIGN[align],
        stickyRight &&
          'sticky right-0 border-l border-l-line bg-white group-hover:bg-slate-50 group-focus:bg-slate-50',
        className,
      )}
    >
      {children}
    </td>
  );
}
