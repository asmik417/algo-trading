// Text input and select with the app's look.
import clsx from 'clsx';
import { forwardRef, type InputHTMLAttributes, type SelectHTMLAttributes } from 'react';

const CONTROL =
  'h-9 rounded-lg border border-line bg-white px-3 text-sm text-ink placeholder:text-ink-faint focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20 disabled:bg-slate-50';

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className, ...rest }, ref) {
    return <input ref={ref} className={clsx(CONTROL, className)} {...rest} />;
  },
);

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  function Select({ className, children, ...rest }, ref) {
    return (
      <select ref={ref} className={clsx(CONTROL, 'pr-8', className)} {...rest}>
        {children}
      </select>
    );
  },
);
