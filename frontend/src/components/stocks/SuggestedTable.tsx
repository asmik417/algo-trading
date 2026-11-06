// Stocks → Algo Suggested: one row per suggestion; click a row for the full stock dialog.
import { formatNumber } from '../../lib/format';
import type { SuggestionSummary } from '../../types/api';
import { useCachedSuggestionHeadlines } from '../../hooks/useCachedHeadlines';
import { Table, TableWrap, Td, Th } from '../ui/Table';
import { MetricCells, MetricHeaders, StockCell, StockHeader } from './SuggestionColumns';
import { TrackButton } from './TrackButton';

interface Props {
  items: SuggestionSummary[];
  onOpen: (item: SuggestionSummary) => void;
  onTrack: (item: SuggestionSummary) => void;
  isTracking: (id: number) => boolean;
}

export function SuggestedTable({ items, onOpen, onTrack, isTracking }: Props) {
  // The decision headline is the row tooltip (available once a row's detail has been opened).
  const headlines = useCachedSuggestionHeadlines(items.map((s) => s.id));
  return (
    <TableWrap>
      <Table>
        <thead>
          <tr>
            <Th align="right">Rank</Th>
            <StockHeader />
            <MetricHeaders withOverall />
            <Th align="center" stickyRight>
              Track
            </Th>
          </tr>
        </thead>
        <tbody>
          {items.map((s) => (
            <tr
              key={s.id}
              title={headlines.get(s.id)}
              tabIndex={0}
              onClick={() => onOpen(s)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && e.target === e.currentTarget) onOpen(s);
              }}
              className="group cursor-pointer hover:bg-slate-50 focus:bg-slate-50 focus:outline-none"
            >
              <Td align="right" className="text-ink-muted">
                {formatNumber(s.rank)}
              </Td>
              <StockCell s={s} />
              <MetricCells s={s} withOverall />
              <Td align="center" stickyRight>
                <TrackButton suggestion={s} loading={isTracking(s.id)} onTrack={() => onTrack(s)} />
              </Td>
            </tr>
          ))}
        </tbody>
      </Table>
    </TableWrap>
  );
}
