// Small dropdown of earlier analyses of the selected pick list under the active strategy.
import { useWatchlistRuns } from '../../hooks/useWatchlist';
import { formatDateTime } from '../../lib/format';
import type { Run } from '../../types/api';
import { Select } from '../ui/Input';

function describe(run: Run): string {
  const n = run.symbols?.length ?? 0;
  const state = run.status === 'done' ? '' : run.status === 'failed' ? ' (failed)' : ' (running)';
  return `${formatDateTime(run.created_at)} · ${n} stock${n === 1 ? '' : 's'}${state}`;
}

export function PreviousAnalyses({
  profileId,
  listId,
  currentRunId,
  onOpen,
}: {
  profileId: number;
  listId: number;
  currentRunId: number | null;
  onOpen: (run: Run) => void;
}) {
  const { data: runs = [], isLoading } = useWatchlistRuns(profileId, { limit: 10, listId });
  const value = runs.some((r) => r.id === currentRunId) ? String(currentRunId) : '';
  return (
    <Select
      aria-label="Previous analyses"
      value={value}
      disabled={isLoading || runs.length === 0}
      onChange={(e) => {
        const run = runs.find((r) => r.id === Number(e.target.value));
        if (run) onOpen(run);
      }}
      className="max-w-xs text-sm"
    >
      <option value="" disabled>
        {isLoading
          ? 'Loading…'
          : runs.length
            ? `Previous analyses (${runs.length})`
            : 'No previous analyses'}
      </option>
      {runs.map((r) => (
        <option key={r.id} value={r.id}>
          {describe(r)}
        </option>
      ))}
    </Select>
  );
}
