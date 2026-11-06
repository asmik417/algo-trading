// Stocks: "Algo Suggested" (the strategy's run output) and "Explore" (every NSE stock), both opening the same stock dialog.
import { Compass, Settings2 } from 'lucide-react';
import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { PageHeader } from '../components/layout/PageHeader';
import { MarketBriefBanner } from '../components/market/MarketBriefBanner';
import { ExploreTable } from '../components/stocks/ExploreTable';
import { MyPicksTab } from '../components/stocks/MyPicksTab';
import { RunStatusBar } from '../components/stocks/RunStatusBar';
import { StockDialog, type StockSelection } from '../components/stocks/StockDialog';
import { SuggestedTable } from '../components/stocks/SuggestedTable';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorNotice } from '../components/ui/ErrorNotice';
import { Skeleton } from '../components/ui/Skeleton';
import { Tabs } from '../components/ui/Tabs';
import { useSuggestions } from '../hooks/useSuggestions';
import { useTrackSuggestion } from '../hooks/useTrackSuggestion';
import { formatDate } from '../lib/format';
import { useActiveProfile } from '../store/activeProfile';
import type { Profile } from '../types/api';

type TabKey = 'suggested' | 'explore' | 'picks';
const HEADINGS: Record<TabKey, string> = {
  suggested: 'Stocks the algo suggests',
  explore: 'Every NSE stock',
  picks: 'Stocks you picked',
};

const TABS: { key: TabKey; label: string }[] = [
  { key: 'suggested', label: 'Algo Suggested' },
  { key: 'explore', label: 'Explore' },
  { key: 'picks', label: 'My Picks' },
];

function SuggestedTab({
  profile,
  onOpen,
}: {
  profile: Profile;
  onOpen: (s: StockSelection) => void;
}) {
  const { data, isLoading, error, refetch } = useSuggestions(profile.id);
  const { track, isTracking } = useTrackSuggestion();
  const run = data?.run ?? null;
  const items = data?.items ?? [];

  return (
    <div className="space-y-4">
      <RunStatusBar profile={profile} latestRun={run} />
      {error ? (
        <ErrorNotice error={error} onRetry={() => void refetch()} />
      ) : isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 6 }, (_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      ) : !run ? (
        <EmptyState
          icon={Compass}
          title="No suggestions yet"
          description={
            <>
              Run the algo under <strong>{profile.name}</strong> to get suggestions.
            </>
          }
        />
      ) : items.length === 0 ? (
        <EmptyState
          icon={Settings2}
          title="Nothing passed your filters"
          description={`No stock passed ${profile.name}'s filters in the run of ${formatDate(run.trading_day)}. Loosen a parameter in Strategies and run again.`}
          action={
            <Link to="/strategies" className="text-sm font-medium text-brand-dark hover:underline">
              Open Strategies
            </Link>
          }
        />
      ) : (
        <SuggestedTable
          items={items}
          onOpen={(s) => onOpen({ kind: 'suggested', id: s.id, symbol: s.symbol })}
          onTrack={(s) => void track(s)}
          isTracking={isTracking}
        />
      )}
    </div>
  );
}

export default function StocksPage() {
  const { profile, isLoading } = useActiveProfile();
  const [params, setParams] = useSearchParams();
  const [selection, setSelection] = useState<StockSelection | null>(null);
  const raw = params.get('tab');
  const tab: TabKey = raw === 'explore' || raw === 'picks' ? raw : 'suggested';

  const setTab = (key: TabKey) =>
    setParams(key === 'suggested' ? {} : { tab: key }, { replace: true });

  if (isLoading) return <Skeleton className="h-40 w-full" />;
  if (!profile) {
    return (
      <EmptyState
        icon={Settings2}
        title="Create a strategy first"
        description="The algo needs a strategy to know which parameters to screen on."
        action={
          <Link to="/strategies" className="text-sm font-medium text-brand-dark hover:underline">
            Go to Strategies
          </Link>
        }
      />
    );
  }

  return (
    <div className="space-y-4">
      <MarketBriefBanner />
      <PageHeader
        title={HEADINGS[tab]}
        description={
          tab === 'suggested' ? (
            <>
              Under <strong>{profile.name}</strong>: {profile.params_summary}
            </>
          ) : tab === 'explore' ? (
            <>
              Click a stock to analyse it under <strong>{profile.name}</strong>.
            </>
          ) : (
            <>
              Analyse your own list under <strong>{profile.name}</strong>, with the same rules as
              the algo.
            </>
          )
        }
      />
      <Tabs tabs={TABS} value={tab} onChange={setTab} label="Stocks view" />
      {tab === 'suggested' ? (
        <SuggestedTab profile={profile} onOpen={setSelection} />
      ) : tab === 'explore' ? (
        <ExploreTable onOpen={(symbol) => setSelection({ kind: 'analyze', symbol })} />
      ) : (
        <MyPicksTab profile={profile} onOpen={setSelection} />
      )}
      <StockDialog selection={selection} onClose={() => setSelection(null)} />
    </div>
  );
}
