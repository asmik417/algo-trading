// Backtest: start a new backtest, follow past ones, and compare two finished ones side by side.
import { useState } from 'react';
import { BacktestForm } from '../components/backtest/BacktestForm';
import { BacktestList } from '../components/backtest/BacktestList';
import { ComparePanel } from '../components/backtest/ComparePanel';
import { PageHeader } from '../components/layout/PageHeader';
import { ErrorNotice } from '../components/ui/ErrorNotice';
import { Skeleton } from '../components/ui/Skeleton';
import { useBacktests } from '../hooks/useBacktests';

export default function BacktestPage() {
  const list = useBacktests(undefined, 50);
  const backtests = list.data ?? [];
  const [selected, setSelected] = useState<number[]>([]);
  const [comparing, setComparing] = useState(false);
  const pair = comparing
    ? selected.map((id) => backtests.find((b) => b.id === id)).filter((b) => b?.status === 'done')
    : [];

  const toggle = (id: number) => {
    setComparing(false);
    setSelected((cur) =>
      cur.includes(id) ? cur.filter((x) => x !== id) : cur.length < 2 ? [...cur, id] : cur,
    );
  };

  return (
    <div className="space-y-4">
      <PageHeader
        title="Backtests"
        description="Replay a strategy over past dates. The engine sees only data up to each scan date, and every pick is simulated with the Tracker's rules."
      />
      <div className="grid items-start gap-6 lg:grid-cols-[360px_minmax(0,1fr)]">
        <BacktestForm />
        <div className="min-w-0 space-y-4">
          {list.error ? (
            <ErrorNotice error={list.error} onRetry={() => void list.refetch()} />
          ) : list.isLoading ? (
            <Skeleton className="h-64 w-full" />
          ) : (
            <BacktestList
              backtests={backtests}
              selected={selected}
              onToggle={toggle}
              onCompare={() => setComparing(true)}
            />
          )}
          {pair.length === 2 && pair[0] && pair[1] && (
            <ComparePanel a={pair[0]} b={pair[1]} onClose={() => setComparing(false)} />
          )}
        </div>
      </div>
    </div>
  );
}
