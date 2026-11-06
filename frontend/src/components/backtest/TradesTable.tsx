// Every simulated trade, sortable by any column. Clicking a row expands it in place with the plan numbers and the
// loss-pattern tags (no dialog).
import clsx from 'clsx';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { Fragment, useMemo, useState } from 'react';
import { EXIT_LABEL, EXIT_TONE } from '../../lib/backtest';
import { pnlClass } from '../../lib/colors';
import { DASH, formatDate, formatINR, formatNumber, formatPct } from '../../lib/format';
import type { BacktestTrade } from '../../types/api';
import { SignalBadge } from '../stocks/SignalBadge';
import { Badge } from '../ui/Badge';
import { Card } from '../ui/Card';
import { Table, TableWrap, Td, Th } from '../ui/Table';

type SortKey = keyof Pick<
  BacktestTrade,
  | 'symbol'
  | 'scan_date'
  | 'entry_date'
  | 'entry_price'
  | 'exit_date'
  | 'exit_price'
  | 'exit_reason'
  | 'pnl'
  | 'pnl_pct'
  | 'r_multiple'
  | 'days_held'
  | 'mfe_pct'
  | 'mae_pct'
  | 'nifty_pct'
  | 'signal'
  | 'score'
>;
const COLUMNS: { key: SortKey; label: string; align: 'left' | 'right' }[] = [
  { key: 'symbol', label: 'Stock', align: 'left' },
  { key: 'scan_date', label: 'Scan', align: 'right' },
  { key: 'entry_date', label: 'Entry date', align: 'right' },
  { key: 'entry_price', label: 'Entry', align: 'right' },
  { key: 'exit_date', label: 'Exit date', align: 'right' },
  { key: 'exit_price', label: 'Exit', align: 'right' },
  { key: 'exit_reason', label: 'Exit reason', align: 'left' },
  { key: 'pnl', label: 'P&L', align: 'right' },
  { key: 'pnl_pct', label: 'P&L %', align: 'right' },
  { key: 'r_multiple', label: 'R', align: 'right' },
  { key: 'days_held', label: 'Days', align: 'right' },
  { key: 'mfe_pct', label: 'MFE', align: 'right' },
  { key: 'mae_pct', label: 'MAE', align: 'right' },
  { key: 'nifty_pct', label: 'Nifty', align: 'right' },
  { key: 'signal', label: 'Signal', align: 'left' },
  { key: 'score', label: 'Score', align: 'right' },
];

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-ink-muted">{label}</dt>
      <dd className="num text-sm font-medium text-ink">{value}</dd>
    </div>
  );
}

export function TradesTable({
  trades,
  tagLabels,
}: {
  trades: BacktestTrade[];
  tagLabels: Map<string, string>;
}) {
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: 'entry_date', dir: 1 });
  const [open, setOpen] = useState<number | null>(null);

  const sorted = useMemo(() => {
    const out = [...trades];
    out.sort((a, b) => {
      const av = a[sort.key],
        bv = b[sort.key];
      if (av === null && bv === null) return a.id - b.id;
      if (av === null) return 1; // unavailable values always last
      if (bv === null) return -1;
      const c =
        typeof av === 'number' && typeof bv === 'number'
          ? av - bv
          : String(av).localeCompare(String(bv));
      return c === 0 ? a.id - b.id : c * sort.dir;
    });
    return out;
  }, [trades, sort]);

  const toggleSort = (key: SortKey) =>
    setSort((s) =>
      s.key === key
        ? { key, dir: s.dir === 1 ? -1 : 1 }
        : { key, dir: key === 'symbol' || key.endsWith('date') ? 1 : -1 },
    );

  return (
    <Card
      title={`Trades (${formatNumber(trades.length)})`}
      right={
        <span className="text-xs text-ink-muted">
          Click a header to sort, a row for its plan and tags
        </span>
      }
    >
      <TableWrap maxHeight="max-h-[36rem]">
        <Table>
          <thead>
            <tr>
              {COLUMNS.map((c) => {
                const active = sort.key === c.key;
                return (
                  <Th key={c.key} align={c.align}>
                    <button
                      type="button"
                      onClick={() => toggleSort(c.key)}
                      aria-sort={active ? (sort.dir === 1 ? 'ascending' : 'descending') : 'none'}
                      className={clsx(
                        'inline-flex items-center gap-1 uppercase hover:text-ink',
                        active && 'text-ink',
                      )}
                    >
                      {c.label}
                      {active &&
                        (sort.dir === 1 ? (
                          <ChevronUp className="h-3 w-3" aria-hidden />
                        ) : (
                          <ChevronDown className="h-3 w-3" aria-hidden />
                        ))}
                    </button>
                  </Th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {sorted.map((t) => {
              const expanded = open === t.id;
              return (
                <Fragment key={t.id}>
                  <tr
                    tabIndex={0}
                    aria-expanded={expanded}
                    onClick={() => setOpen(expanded ? null : t.id)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        setOpen(expanded ? null : t.id);
                      }
                    }}
                    className={clsx(
                      'cursor-pointer hover:bg-slate-50 focus:bg-slate-50 focus:outline-none',
                      expanded && 'bg-slate-50',
                    )}
                  >
                    <Td className="font-semibold text-ink">{t.symbol}</Td>
                    <Td align="right">{formatDate(t.scan_date)}</Td>
                    <Td align="right">{formatDate(t.entry_date)}</Td>
                    <Td align="right">{formatINR(t.entry_price)}</Td>
                    <Td align="right">{formatDate(t.exit_date)}</Td>
                    <Td align="right">{formatINR(t.exit_price)}</Td>
                    <Td>
                      <Badge tone={EXIT_TONE[t.exit_reason]}>{EXIT_LABEL[t.exit_reason]}</Badge>
                    </Td>
                    <Td align="right" className={pnlClass(t.pnl)}>
                      {formatINR(t.pnl, { signed: true })}
                    </Td>
                    <Td align="right" className={pnlClass(t.pnl_pct)}>
                      {formatPct(t.pnl_pct)}
                    </Td>
                    <Td align="right" className={pnlClass(t.r_multiple)}>
                      {t.r_multiple === null ? DASH : `${formatNumber(t.r_multiple, 2)}`}
                    </Td>
                    <Td align="right">{formatNumber(t.days_held)}</Td>
                    <Td align="right">{formatPct(t.mfe_pct)}</Td>
                    <Td align="right">{formatPct(t.mae_pct)}</Td>
                    <Td align="right" className={pnlClass(t.nifty_pct)}>
                      {formatPct(t.nifty_pct)}
                    </Td>
                    <Td>
                      <SignalBadge signal={t.signal} />
                    </Td>
                    <Td align="right">{formatNumber(t.score, 1)}</Td>
                  </tr>
                  {expanded && (
                    <tr className="bg-slate-50" aria-label={`${t.symbol} plan and tags`}>
                      <td colSpan={COLUMNS.length} className="border-b border-line px-4 py-3">
                        <dl className="grid grid-cols-2 gap-x-6 gap-y-2 sm:grid-cols-4 lg:grid-cols-8">
                          <Fact label="Quantity" value={formatNumber(t.qty)} />
                          <Fact label="Invested" value={formatINR(t.invested)} />
                          <Fact label="Stop-loss" value={formatINR(t.stop_loss)} />
                          <Fact label="Target" value={formatINR(t.target)} />
                          <Fact label="Planned exit" value={formatDate(t.planned_exit_date)} />
                          <Fact label="Stage" value={t.stage} />
                          <Fact label="Market cap" value={t.market_cap_bucket} />
                          <Fact label="Sector" value={t.sector ?? DASH} />
                        </dl>
                        <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs text-ink-muted">
                          Loss patterns:
                          {t.tags.length === 0 ? (
                            <span>
                              {t.pnl < 0 && t.exit_reason !== 'open'
                                ? 'none tagged'
                                : 'not a closed loss'}
                            </span>
                          ) : (
                            t.tags.map((g) => (
                              <Badge key={g} tone="red">
                                {tagLabels.get(g) ?? g}
                              </Badge>
                            ))
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </Table>
      </TableWrap>
    </Card>
  );
}
