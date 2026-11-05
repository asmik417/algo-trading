// Small dropdown of earlier My Picks runs for the active strategy, so a saved list can be reopened.
import { useWatchlistRuns } from '../../hooks/useWatchlist';
import { formatDateTime } from '../../lib/format';
import type { Run } from '../../types/api';
import { Select } from '../ui/Input';

function describe(run: Run): string {
  const symbols = run.symbols ?? [];
  const head = symbols.slice(0, 3).join(', ') + (symbols.length > 3 ? ', …' : '');
  const state = run.status === 'done' ? '' : run.status === 'failed' ? ' (failed)' : ' (running)';
  return `${formatDateTime(run.created_at)} · ${symbols.length} stock${symbols.length === 1 ? '' : 's'}: ${head}${state}`;
}

export function PreviousAnalyses({
  profileId,
  currentRunId,
  onOpen,
}: {
  profileId: number;
  currentRunId: number | null;
  onOpen: (run: Run) => void;
}) {
  const { data: runs = [], isLoading } = useWatchlistRuns(profileId, 10);
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
