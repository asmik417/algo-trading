// Columns shared by the Algo Suggested and My Picks tables, so both always show the same numbers the same way.
import { pnlClass } from '../../lib/colors';
import { formatDate, formatINR, formatMultiple, formatNumber, formatPct } from '../../lib/format';
import type { SuggestionSummary } from '../../types/api';
import { Td, Th } from '../ui/Table';
import { ScoreBar } from './ScoreBar';
import { SignalBadge } from './SignalBadge';
import { OverallBadge } from './VerdictParts';

export function StockHeader() {
  return <Th>Stock</Th>;
}

export function StockCell({ s }: { s: SuggestionSummary }) {
  return (
    <Td>
      <div className="font-semibold text-ink">{s.symbol}</div>
      <div className="text-xs text-ink-muted">
        {s.market_cap_bucket}
        {s.sector ? ` · ${s.sector}` : ''}
      </div>
    </Td>
  );
}

/** Signal … Vol×. `withOverall` adds the Overall verdict column right after Signal (Algo Suggested). */
export function MetricHeaders({ withOverall = false }: { withOverall?: boolean }) {
  return (
    <>
      <Th>Signal</Th>
      {withOverall && <Th>Overall</Th>}
      <Th>Stage</Th>
      <Th align="right">Score</Th>
      <Th align="right">Price</Th>
      <Th align="right">Entry</Th>
      <Th align="right">Stop</Th>
      <Th align="right">Target</Th>
      <Th align="right">R:R</Th>
      <Th align="right">Exit by</Th>
      <Th align="right">Profit YoY</Th>
      <Th align="right">1M</Th>
      <Th align="right">3M</Th>
      <Th align="right">Vol×</Th>
    </>
  );
}

export const METRIC_COLUMN_COUNT = 13;

export function MetricCells({
  s,
  withOverall = false,
}: {
  s: SuggestionSummary;
  withOverall?: boolean;
}) {
  return (
    <>
      <Td>
        <SignalBadge signal={s.signal} />
      </Td>
      {withOverall && (
        <Td>
          <OverallBadge verdict={s.verdict} />
        </Td>
      )}
      <Td className="text-ink-muted">{s.stage}</Td>
      <Td align="right">
        <ScoreBar score={s.score} />
      </Td>
      <Td align="right">{formatINR(s.price)}</Td>
      <Td align="right">{formatINR(s.entry_optimal)}</Td>
      <Td align="right" className="text-loss">
        {formatINR(s.stop_loss)}
      </Td>
      <Td align="right" className="text-brand-dark">
        {formatINR(s.target)}
      </Td>
      <Td align="right">{formatNumber(s.risk_reward, 1)}</Td>
      <Td align="right">{formatDate(s.planned_exit_date)}</Td>
      <Td align="right" className={pnlClass(s.profit_yoy_pct)}>
        {formatPct(s.profit_yoy_pct)}
      </Td>
      <Td align="right" className={pnlClass(s.change_1m_pct)}>
        {formatPct(s.change_1m_pct)}
      </Td>
      <Td align="right" className={pnlClass(s.change_3m_pct)}>
        {formatPct(s.change_3m_pct)}
      </Td>
      <Td align="right">{formatMultiple(s.volume_ratio_20d)}</Td>
    </>
  );
}
