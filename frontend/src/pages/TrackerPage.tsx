// Tracker: paper positions simulated with fake money, their statistics, and the actions that change them.
import { Briefcase } from 'lucide-react';
import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { DailyUpdateButton } from '../components/tracker/DailyUpdateButton';
import { ChangeExitDialog } from '../components/tracker/ChangeExitDialog';
import { CloseDialog } from '../components/tracker/CloseDialog';
import { NoteDialog } from '../components/tracker/NoteDialog';
import { PositionDrawer, type DrawerAction } from '../components/tracker/PositionDrawer';
import { PositionsTable } from '../components/tracker/PositionsTable';
import { StatsRow } from '../components/tracker/StatsRow';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorNotice } from '../components/ui/ErrorNotice';
import { Skeleton } from '../components/ui/Skeleton';
import { Tabs, type TabItem } from '../components/ui/Tabs';
import { usePositions, useProfileStats } from '../hooks/usePositions';
import { useActiveProfile } from '../store/activeProfile';
import type { Position } from '../types/api';
import type { PositionFilter } from '../types/ui';

const EMPTY_TEXT: Record<PositionFilter, string> = {
  open: 'No open positions.',
  due: 'Nothing is due. Positions show up here on their planned exit date.',
  closed: 'No closed positions yet.',
  all: 'No positions yet.',
};

export default function TrackerPage() {
  const { profile, isLoading: profileLoading } = useActiveProfile();
  const profileId = profile?.id;
  const [tab, setTab] = useState<PositionFilter>('open');
  const [params, setParams] = useSearchParams();
  const [dialog, setDialog] = useState<{ action: DrawerAction; position: Position } | null>(null);

  const stats = useProfileStats(profileId);
  const list = usePositions(profileId, tab);

  const openId = Number(params.get('position')) || null;
  const openDrawer = (id: number) => setParams({ position: String(id) }, { replace: true });
  const closeDrawer = () => setParams({}, { replace: true });
  const clearDialog = () => setDialog(null);

  const s = stats.data;
  const tabs: TabItem<PositionFilter>[] = [
    { key: 'open', label: 'Open', count: s?.open },
    { key: 'due', label: 'Due', count: s?.due },
    { key: 'closed', label: 'Closed', count: s?.closed },
    { key: 'all', label: 'All', count: s ? s.open + s.due + s.closed : undefined },
  ];

  if (profileLoading) return <Skeleton className="h-40 w-full" />;
  if (!profile) {
    return (
      <EmptyState
        icon={Briefcase}
        title="Create a strategy first"
        description="Paper positions belong to a strategy."
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
      <DailyUpdateButton />
      <StatsRow stats={s} loading={stats.isLoading} />
      {stats.error && <ErrorNotice error={stats.error} onRetry={() => void stats.refetch()} />}
      <Tabs tabs={tabs} value={tab} onChange={setTab} label="Positions" />

      {list.error ? (
        <ErrorNotice error={list.error} onRetry={() => void list.refetch()} />
      ) : list.isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }, (_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      ) : (list.data ?? []).length === 0 ? (
        <EmptyState
          icon={Briefcase}
          title={EMPTY_TEXT[tab]}
          description="Track a stock from Stocks → Algo Suggested to simulate it with paper money."
          action={
            <Link to="/stocks" className="text-sm font-medium text-brand-dark hover:underline">
              Go to Stocks
            </Link>
          }
        />
      ) : (
        <PositionsTable
          positions={list.data ?? []}
          onOpen={(p) => openDrawer(p.id)}
          onExtend={(p) => setDialog({ action: 'extend', position: p })}
          onClose={(p) => setDialog({ action: 'close', position: p })}
        />
      )}

      <PositionDrawer
        positionId={openId}
        onClose={closeDrawer}
        onAction={(action, position) => setDialog({ action, position })}
      />
      <ChangeExitDialog
        position={
          dialog && (dialog.action === 'extend' || dialog.action === 'shorten')
            ? dialog.position
            : null
        }
        mode={dialog?.action === 'shorten' ? 'shorten' : 'extend'}
        onClose={clearDialog}
      />
      <CloseDialog
        position={dialog?.action === 'close' ? dialog.position : null}
        onClose={clearDialog}
      />
      <NoteDialog
        position={dialog?.action === 'note' ? dialog.position : null}
        onClose={clearDialog}
      />
    </div>
  );
}
