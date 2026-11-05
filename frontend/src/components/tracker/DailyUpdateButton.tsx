// Top-bar action: run the daily mark-to-market job now and show when it last ran.
import { RefreshCw } from 'lucide-react';
import { errorMessage } from '../../api/client';
import { useJobStatus, useRunDailyUpdate } from '../../hooks/useJobs';
import { formatDateTime } from '../../lib/format';
import { TopBarActions } from '../layout/topBarSlot';
import { Button } from '../ui/Button';
import { useToast } from '../ui/Toast';

export function DailyUpdateButton() {
  const toast = useToast();
  const { data: status } = useJobStatus();
  const run = useRunDailyUpdate();
  const busy = run.isPending || status?.running === true;

  const onClick = async () => {
    try {
      const result = await run.mutateAsync();
      if (result.started) toast.info('Daily update started. Positions refresh in a few seconds.');
      else toast.info(`Daily update not started: ${result.reason ?? 'already running'}.`);
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };

  return (
    <TopBarActions>
      <span className="hidden text-xs text-ink-muted md:inline">
        Last update: {formatDateTime(status?.last_daily_update)}
      </span>
      <Button size="sm" variant="secondary" loading={busy} onClick={onClick}>
        {!busy && <RefreshCw className="h-4 w-4" aria-hidden />}
        {busy ? 'Updating…' : 'Run daily update'}
      </Button>
    </TopBarActions>
  );
}
