// Latest run summary, the "Run algo now" button, and live progress while a run is in flight.
import { Play } from 'lucide-react';
import { useState } from 'react';
import { errorMessage } from '../../api/client';
import { isRunActive, useRunStatus, useRuns, useStartRun } from '../../hooks/useRuns';
import { formatDate, formatDateTime, formatNumber } from '../../lib/format';
import type { Profile, Run } from '../../types/api';
import { Button } from '../ui/Button';
import { RunProgress } from './RunProgress';
import { useToast } from '../ui/Toast';

function Funnel({ run }: { run: Run }) {
  return (
    <span className="num">
      {formatNumber(run.universe_size)} screened → {formatNumber(run.scored_size)} scored →{' '}
      {formatNumber(run.passed_size)} passed
    </span>
  );
}

export function RunStatusBar({ profile, latestRun }: { profile: Profile; latestRun: Run | null }) {
  const toast = useToast();
  const start = useStartRun();
  const newest = useRuns(profile.id, 1).data?.[0];
  const [startedId, setStartedId] = useState<number | null>(null);

  // Follow the run we just started, or one that was already in flight when the page opened.
  const followId = startedId ?? (newest && isRunActive(newest) ? newest.id : null);
  const followed = useRunStatus(followId).data;
  const live = followed && followed.profile_id === profile.id ? followed : undefined;
  const active = isRunActive(live);
  const failed = live?.status === 'failed' ? live : undefined;
  const shown = (live?.status === 'done' ? live : latestRun) ?? latestRun;

  const onRun = async () => {
    try {
      const run = await start.mutateAsync({ profileId: profile.id });
      setStartedId(run.id);
      toast.info(`Algo run started for ${profile.name}`);
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };

  return (
    <div className="rounded-lg border border-line bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0 text-sm">
          {shown ? (
            <>
              <div className="font-medium text-ink">
                Latest run · data as of {formatDate(shown.trading_day)}
              </div>
              <div className="mt-0.5 text-ink-muted">
                <Funnel run={shown} />
                <span className="ml-3 text-xs">Finished {formatDateTime(shown.finished_at)}</span>
              </div>
            </>
          ) : (
            <div className="text-ink-muted">
              No run yet under <strong className="text-ink">{profile.name}</strong>.
            </div>
          )}
        </div>
        <Button onClick={onRun} loading={start.isPending || active} disabled={active}>
          {!(start.isPending || active) && <Play className="h-4 w-4" aria-hidden />}
          {active ? 'Running…' : 'Run algo now'}
        </Button>
      </div>
      {active && live && <RunProgress run={live} label="Algo run progress" />}
      {failed && (
        <p role="alert" className="mt-3 rounded-lg bg-loss-soft px-3 py-2 text-sm text-loss">
          The run failed{failed.error ? `: ${failed.error}` : '.'}
        </p>
      )}
    </div>
  );
}
