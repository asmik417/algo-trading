// My Picks results: same columns as Algo Suggested plus a Verdict. Unknown symbols get a muted error row.
import { isMiss } from '../../lib/watchlist';
import type { WatchlistHit, WatchlistItem } from '../../types/api';
import { Badge } from '../ui/Badge';
import { Table, TableWrap, Td, Th } from '../ui/Table';
import {
  METRIC_COLUMN_COUNT,
  MetricCells,
  MetricHeaders,
  StockCell,
  StockHeader,
} from './SuggestionColumns';
import { TrackButton } from './TrackButton';

interface Props {
  items: WatchlistItem[];
  onOpen: (item: WatchlistHit) => void;
  onTrack: (item: WatchlistHit) => void;
  isTracking: (id: number) => boolean;
}

function Verdict({ item }: { item: WatchlistHit }) {
  const first = item.filters.failures[0];
  return (
    <div className="max-w-[15rem]">
      {item.filters.passed ? <Badge tone="green">Passes</Badge> : <Badge tone="red">Fails</Badge>}
      {first && (
        <div
          className="mt-0.5 truncate text-xs text-ink-muted"
          title={item.filters.failures.join('\n')}
        >
          {first}
        </div>
      )}
    </div>
  );
}

export function WatchlistTable({ items, onOpen, onTrack, isTracking }: Props) {
  return (
    <TableWrap>
      <Table>
        <thead>
          <tr>
            <Th align="right">#</Th>
            <StockHeader />
            <Th>Verdict</Th>
            <MetricHeaders />
            <Th align="center" stickyRight>
              Track
            </Th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, i) =>
            isMiss(item) ? (
              // WatchlistMiss: only `symbol` and `error` carry data (contract, "Watchlist runs").
              <tr key={`err-${item.symbol}-${i}`} className="group">
                <Td align="right" className="text-ink-faint">
                  {i + 1}
                </Td>
                <Td className="font-semibold text-ink-muted">{item.symbol}</Td>
                <Td colSpan={METRIC_COLUMN_COUNT + 1} className="text-sm italic text-ink-muted">
                  Error: {item.error}
                </Td>
                <Td stickyRight />
              </tr>
            ) : (
              <tr
                key={item.id}
                tabIndex={0}
                onClick={() => onOpen(item)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && e.target === e.currentTarget) onOpen(item);
                }}
                className="group cursor-pointer hover:bg-slate-50 focus:bg-slate-50 focus:outline-none"
              >
                <Td align="right" className="text-ink-muted">
                  {i + 1}
                </Td>
                <StockCell s={item} />
                <Td>
                  <Verdict item={item} />
                </Td>
                <MetricCells s={item} />
                <Td align="center" stickyRight>
                  <TrackButton
                    suggestion={item}
                    loading={isTracking(item.id)}
                    onTrack={() => onTrack(item)}
                  />
                </Td>
              </tr>
            ),
          )}
        </tbody>
      </Table>
    </TableWrap>
  );
}
