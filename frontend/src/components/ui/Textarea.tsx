// Multi-line text input (reasons, notes, reviews).
import clsx from 'clsx';
import { forwardRef, type TextareaHTMLAttributes } from 'react';

export const Textarea = forwardRef<
  HTMLTextAreaElement,
  TextareaHTMLAttributes<HTMLTextAreaElement>
>(function Textarea({ className, ...rest }, ref) {
  return (
    <textarea
      ref={ref}
      rows={3}
      className={clsx(
        'w-full rounded-lg border border-line bg-white px-3 py-2 text-sm text-ink placeholder:text-ink-faint focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20',
        className,
      )}
      {...rest}
    />
  );
});
