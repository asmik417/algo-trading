// Stocks → Explore: every NSE stock with search, sort and paging. Click a row to analyse it under the active strategy.
import {
  ChevronLeft,
  ChevronRight,
  ArrowDownWideNarrow,
  ArrowUpNarrowWide,
  Search,
} from 'lucide-react';
import { useState } from 'react';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { useStocks } from '../../hooks/useStocks';
import { pnlClass } from '../../lib/colors';
import { formatDate, formatINR, formatMultiple, formatNumber, formatPct } from '../../lib/format';
import type { StockSortKey } from '../../types/ui';
import { Button } from '../ui/Button';
import { EmptyState } from '../ui/EmptyState';
import { ErrorNotice } from '../ui/ErrorNotice';
import { Input, Select } from '../ui/Input';
import { Skeleton } from '../ui/Skeleton';
import { Table, TableWrap, Td, Th } from '../ui/Table';

const PAGE_SIZE = 50;
const SORT_OPTIONS: { key: StockSortKey; label: string }[] = [
  { key: 'change_1m_pct', label: '1-month change' },
  { key: 'change_1d_pct', label: '1-day change' },
  { key: 'change_1w_pct', label: '1-week change' },
  { key: 'change_3m_pct', label: '3-month change' },
  { key: 'dist_from_52w_high_pct', label: 'Distance from 52-week high' },
  { key: 'volume_ratio_20d', label: 'Volume vs 20-day average' },
  { key: 'avg_turnover_lacs', label: 'Average turnover' },
  { key: 'close', label: 'Price' },
  { key: 'symbol', label: 'Symbol (A-Z)' },
];

export function ExploreTable({ onOpen }: { onOpen: (symbol: string) => void }) {
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState<StockSortKey>('change_1m_pct');
  const [order, setOrder] = useState<'asc' | 'desc'>('desc');
  const debouncedSearch = useDebouncedValue(search.trim(), 300);

  // The page number belongs to one search+sort combination; any change starts again from page 1.
  const queryId = `${debouncedSearch}|${sort}|${order}`;
  const [pageState, setPageState] = useState({ queryId, page: 0 });
  const page = pageState.queryId === queryId ? pageState.page : 0;
  const setPage = (update: (p: number) => number) => setPageState({ queryId, page: update(page) });

  const { data, isLoading, isFetching, error, refetch } = useStocks({
    search: debouncedSearch,
    sort,
    order,
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
  });

  const total = data?.total ?? 0;
  const from = total === 0 ? 0 : page * PAGE_SIZE + 1;
  const to = Math.min(total, (page + 1) * PAGE_SIZE);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative w-full max-w-xs">
          <Search
            className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-ink-faint"
            aria-hidden
          />
          <Input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search NSE symbol, e.g. RELI"
            aria-label="Search stocks"
            className="w-full pl-9"
          />
        </div>
        <label className="flex items-center gap-2 text-sm text-ink-muted">
          Sort by
          <Select
            value={sort}
            onChange={(e) => setSort(e.target.value as StockSortKey)}
            aria-label="Sort by"
          >
            {SORT_OPTIONS.map((o) => (
              <option key={o.key} value={o.key}>
                {o.label}
              </option>
            ))}
          </Select>
        </label>
        <Button
          variant="secondary"
          onClick={() => setOrder((o) => (o === 'desc' ? 'asc' : 'desc'))}
          aria-label={
            order === 'desc'
              ? 'Sorted high to low; switch to low to high'
              : 'Sorted low to high; switch to high to low'
          }
        >
          {order === 'desc' ? (
            <ArrowDownWideNarrow className="h-4 w-4" aria-hidden />
          ) : (
            <ArrowUpNarrowWide className="h-4 w-4" aria-hidden />
          )}
          {order === 'desc' ? 'High → low' : 'Low → high'}
        </Button>
        <span className="ml-auto text-xs text-ink-muted">
          {data && `Prices as of ${formatDate(data.trading_day)}`}
        </span>
      </div>

      {error ? (
        <ErrorNotice error={error} onRetry={() => void refetch()} />
      ) : isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 8 }, (_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      ) : total === 0 ? (
        <EmptyState
          icon={Search}
          title="No stocks match your search"
          description="Try a shorter symbol or clear the search box."
        />
      ) : (
        <>
          <TableWrap
            className={isFetching ? 'opacity-70 transition-opacity' : 'transition-opacity'}
          >
            <Table>
              <thead>
                <tr>
                  <Th>Stock</Th>
                  <Th align="right">Close</Th>
                  <Th align="right">1D</Th>
                  <Th align="right">1W</Th>
                  <Th align="right">1M</Th>
                  <Th align="right">3M</Th>
                  <Th align="right">From 52w high</Th>
                  <Th align="right">Vol×</Th>
                  <Th align="right">Avg turnover</Th>
                </tr>
              </thead>
              <tbody>
                {data?.items.map((r) => (
                  <tr
                    key={r.symbol}
                    tabIndex={0}
                    onClick={() => onOpen(r.symbol)}
                    onKeyDown={(e) => e.key === 'Enter' && onOpen(r.symbol)}
                    className="cursor-pointer hover:bg-slate-50 focus:bg-slate-50 focus:outline-none"
                  >
                    <Td className="font-semibold text-ink">{r.symbol}</Td>
                    <Td align="right">{formatINR(r.close)}</Td>
                    <Td align="right" className={pnlClass(r.change_1d_pct)}>
                      {formatPct(r.change_1d_pct)}
                    </Td>
                    <Td align="right" className={pnlClass(r.change_1w_pct)}>
                      {formatPct(r.change_1w_pct)}
                    </Td>
                    <Td align="right" className={pnlClass(r.change_1m_pct)}>
                      {formatPct(r.change_1m_pct)}
                    </Td>
                    <Td align="right" className={pnlClass(r.change_3m_pct)}>
                      {formatPct(r.change_3m_pct)}
                    </Td>
                    <Td align="right" className={pnlClass(r.dist_from_52w_high_pct)}>
                      {formatPct(r.dist_from_52w_high_pct)}
                    </Td>
                    <Td align="right">{formatMultiple(r.volume_ratio_20d)}</Td>
                    <Td align="right">
                      {r.avg_turnover_lacs === null
                        ? '—'
                        : `₹${formatNumber(r.avg_turnover_lacs)} L`}
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </TableWrap>
          <div className="flex items-center justify-between text-sm text-ink-muted">
            <span className="num">
              Showing {formatNumber(from)}–{formatNumber(to)} of {formatNumber(total)}
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                disabled={page === 0}
                onClick={() => setPage((p) => p - 1)}
              >
                <ChevronLeft className="h-4 w-4" aria-hidden /> Previous
              </Button>
              <Button
                variant="secondary"
                size="sm"
                disabled={to >= total}
                onClick={() => setPage((p) => p + 1)}
              >
                Next <ChevronRight className="h-4 w-4" aria-hidden />
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
