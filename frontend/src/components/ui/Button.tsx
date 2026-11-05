// The one button used everywhere. `loading` shows a spinner and blocks clicks.
import clsx from 'clsx';
import { Loader2 } from 'lucide-react';
import { forwardRef, type ButtonHTMLAttributes } from 'react';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';
type Size = 'sm' | 'md';

const VARIANTS: Record<Variant, string> = {
  primary: 'bg-brand text-white hover:bg-brand-dark disabled:bg-brand/50',
  secondary: 'border border-line bg-white text-ink hover:bg-slate-50 disabled:text-ink-faint',
  ghost: 'text-ink-muted hover:bg-slate-100 hover:text-ink disabled:text-ink-faint',
  danger: 'bg-loss text-white hover:bg-loss/90 disabled:bg-loss/50',
};
const SIZES: Record<Size, string> = { sm: 'h-8 px-3 text-xs', md: 'h-9 px-4 text-sm' };

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, Props>(function Button(
  {
    variant = 'primary',
    size = 'md',
    loading = false,
    disabled,
    className,
    children,
    type = 'button',
    ...rest
  },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      className={clsx(
        'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand/40 disabled:cursor-not-allowed',
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
      {...rest}
    >
      {loading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
      {children}
    </button>
  );
});
