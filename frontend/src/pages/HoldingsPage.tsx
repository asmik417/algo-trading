// Placeholder for the future live-trading module (broker holdings, automatic buy/sell). No API calls yet.
import { Wallet } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Badge } from '../components/ui/Badge';

export default function HoldingsPage() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <div className="flex max-w-md flex-col items-center rounded-lg border border-dashed border-line bg-white px-8 py-12 text-center">
        <span className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-ink-muted">
          <Wallet className="h-6 w-6" aria-hidden />
        </span>
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold text-ink">Holdings</h2>
          <Badge tone="amber">Coming soon</Badge>
        </div>
        <p className="mt-2 text-sm text-ink">
          Live broker holdings and automatic buy/sell will appear here.
        </p>
        <p className="mt-3 text-xs text-ink-muted">
          Until then, every trade in this app is paper money. See{' '}
          <Link to="/tracker" className="font-medium text-brand-dark hover:underline">
            Tracker
          </Link>
          .
        </p>
      </div>
    </div>
  );
}
