// Small coloured pill: signals, statuses, tags.
import clsx from 'clsx';
import type { ReactNode } from 'react';
import { TONE_CLASSES, type Tone } from '../../lib/colors';

export function Badge({
  tone = 'grey',
  className,
  children,
}: {
  tone?: Tone;
  className?: string;
  children: ReactNode;
}) {
  return (
    <span
      className={clsx(
        'inline-flex items-center whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium',
        TONE_CLASSES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
