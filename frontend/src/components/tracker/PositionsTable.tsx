// Tracker table: one row per paper position. Click a row for the drawer; Extend / Close are quick actions on live rows.
import { Link } from 'react-router-dom';
import { pnlClass } from '../../lib/colors';
import { formatDate, formatINR, formatNumber, formatPct } from '../../lib/format';
import type { Position } from '../../types/api';
import { Button } from '../ui/Button';
import { Table, TableWrap, Td, Th } from '../ui/Table';
import { SignalBadge } from '../stocks/SignalBadge';
import { StatusBadge } from './StatusBadge';

interface Props {
  positions: Position[];
  onOpen: (p: Position) => void;
  onExtend: (p: Position) => void;
  onClose: (p: Position) => void;
}

export function PositionsTable({ positions, onOpen, onExtend, onClose }: Props) {
  return (
    <TableWrap maxHeight="max-h-[calc(100vh-26rem)]">
      <Table>
        <thead>
          <tr>
            <Th>Stock</Th>
            <Th align="right">Opened</Th>
            <Th align="right">Entry</Th>
            <Th align="right">Qty</Th>
            <Th align="right">Invested</Th>
            <Th align="right">Last close</Th>
            <Th align="right">Value</Th>
            <Th align="right">P&amp;L</Th>
            <Th align="right">Target</Th>
            <Th align="right">Stop</Th>
            <Th align="right">Exit by</Th>
            <Th align="right">Days left</Th>
            <Th>Status</Th>
            <Th align="center" stickyRight>
              Actions
            </Th>
          </tr>
        </thead>
        <tbody>
          {positions.map((p) => {
            const live = p.status !== 'closed';
            return (
              <tr
                key={p.id}
                tabIndex={0}
                onClick={() => onOpen(p)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && e.target === e.currentTarget) onOpen(p);
                }}
                className="group cursor-pointer hover:bg-slate-50 focus:bg-slate-50 focus:outline-none"
              >
                <Td>
                  <div className="font-semibold text-ink">{p.symbol}</div>
                  {p.signal && <SignalBadge signal={p.signal} />}
                </Td>
                <Td align="right">{formatDate(p.opened_on)}</Td>
                <Td align="right">{formatINR(p.entry_price)}</Td>
                <Td align="right">{formatNumber(p.qty)}</Td>
                <Td align="right">{formatINR(p.invested)}</Td>
                <Td align="right">{formatINR(p.last_close)}</Td>
                <Td align="right">{formatINR(p.current_value)}</Td>
                <Td align="right">
                  <div className={pnlClass(p.pnl)}>{formatINR(p.pnl, { signed: true })}</div>
                  <div className={`text-xs ${pnlClass(p.pnl_pct)}`}>{formatPct(p.pnl_pct)}</div>
                </Td>
                <Td align="right">{formatINR(p.target)}</Td>
                <Td align="right">{formatINR(p.stop_loss)}</Td>
                <Td align="right">{formatDate(p.planned_exit_date)}</Td>
                <Td align="right">{live ? formatNumber(p.days_to_exit) : '—'}</Td>
                <Td>
                  <StatusBadge position={p} />
                </Td>
                <Td align="center" stickyRight>
                  {live ? (
                    <div className="flex justify-center gap-1.5">
                      <Button
                        size="sm"
                        variant={p.status === 'due' ? 'primary' : 'secondary'}
                        onClick={(e) => {
                          e.stopPropagation();
                          onExtend(p);
                        }}
                      >
                        Extend
                      </Button>
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={(e) => {
                          e.stopPropagation();
                          onClose(p);
                        }}
                      >
                        Close
                      </Button>
                    </div>
                  ) : p.needs_review ? (
                    <Link
                      to="/losses"
                      onClick={(e) => e.stopPropagation()}
                      className="text-xs font-medium text-loss hover:underline"
                    >
                      Needs review
                    </Link>
                  ) : (
                    <span className="text-ink-faint">—</span>
                  )}
                </Td>
              </tr>
            );
          })}
        </tbody>
      </Table>
    </TableWrap>
  );
}
