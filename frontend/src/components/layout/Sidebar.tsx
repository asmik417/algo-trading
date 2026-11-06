// 240px navigation column (icons only below 1024px): brand, active-strategy dropdown, the modules, data-date footer, sign out.
import clsx from 'clsx';
import {
  Activity,
  Briefcase,
  ClipboardCheck,
  Database,
  History,
  LogOut,
  SlidersHorizontal,
  TrendingDown,
  TrendingUp,
  Wallet,
  type LucideIcon,
} from 'lucide-react';
import { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { USE_MOCKS } from '../../api/client';
import { useJobStatus } from '../../hooks/useJobs';
import { formatDate } from '../../lib/format';
import { useAuth } from '../../store/auth';
import { useToast } from '../ui/Toast';
import { StrategyDropdown } from './StrategyDropdown';

const NAV: { to: string; label: string; icon: LucideIcon }[] = [
  { to: '/stocks', label: 'Stocks', icon: TrendingUp },
  { to: '/tracker', label: 'Tracker', icon: Briefcase },
  { to: '/holdings', label: 'Holdings', icon: Wallet },
  { to: '/scorecard', label: 'Scorecard', icon: ClipboardCheck },
  { to: '/losses', label: 'Loss Analysis', icon: TrendingDown },
  { to: '/backtest', label: 'Backtest', icon: History },
  { to: '/strategies', label: 'Strategies', icon: SlidersHorizontal },
];

/** The last market day the data covers. It can lag behind today, so never call it "Today". */
function DataDate() {
  const { data, isLoading } = useJobStatus();
  const label = isLoading ? 'Data as of …' : `Data as of ${formatDate(data?.last_trading_day)}`;
  return (
    <div className="flex items-center gap-2 text-xs text-ink-muted" title={label}>
      <Database className="h-4 w-4 shrink-0" aria-hidden />
      <span className="hidden lg:inline">{label}</span>
    </div>
  );
}

function SignOut() {
  const { state, signOut } = useAuth();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const username = state.status === 'authenticated' ? state.user.username : null;

  const onClick = async () => {
    setBusy(true);
    try {
      await signOut();
    } catch {
      toast.error('Could not reach the server, but you are signed out in this browser.');
    }
  };

  return (
    <div className="border-t border-line px-3 py-3 lg:px-4">
      {username && (
        <p className="mb-2 hidden truncate text-xs text-ink-muted lg:block">
          Signed in as <strong className="font-medium text-ink">{username}</strong>
        </p>
      )}
      <button
        type="button"
        onClick={onClick}
        disabled={busy}
        title="Sign out"
        className="flex w-full items-center justify-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-ink-muted transition hover:bg-slate-50 hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-brand/40 disabled:opacity-60 lg:justify-start"
      >
        <LogOut className="h-5 w-5 shrink-0" aria-hidden />
        <span className="hidden lg:inline">Sign out</span>
      </button>
    </div>
  );
}

export function Sidebar() {
  return (
    <aside className="relative z-20 flex w-16 shrink-0 flex-col border-r border-line bg-white lg:w-60">
      <div className="flex h-14 items-center gap-2 border-b border-line px-4 lg:px-5">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand text-white">
          <Activity className="h-5 w-5" aria-hidden />
        </span>
        <span className="hidden text-base font-semibold text-ink lg:inline">Trade Assistant</span>
      </div>

      <StrategyDropdown />

      <nav aria-label="Main" className="flex-1 space-y-1 px-3 lg:px-4">
        {NAV.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            title={label}
            className={({ isActive }) =>
              clsx(
                'flex items-center justify-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition lg:justify-start',
                isActive
                  ? 'bg-brand-soft text-brand-dark'
                  : 'text-ink-muted hover:bg-slate-50 hover:text-ink',
              )
            }
          >
            <Icon className="h-5 w-5 shrink-0" aria-hidden />
            <span className="hidden lg:inline">{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="space-y-2 border-t border-line px-4 py-3">
        <DataDate />
        {USE_MOCKS && (
          <span className="inline-block rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-800">
            <span className="lg:hidden">Mock</span>
            <span className="hidden lg:inline">Mock data</span>
          </span>
        )}
      </div>

      <SignOut />
    </aside>
  );
}
