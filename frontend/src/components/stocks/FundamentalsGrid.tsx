// Key company numbers in a compact grid. Anything the backend could not get shows "—".
import { DASH, formatCrore, formatNumber, formatPct } from '../../lib/format';
import type { Fundamentals } from '../../types/api';

function Cell({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-50 px-3 py-2">
      <div className="text-xs text-ink-muted">{label}</div>
      <div className="num mt-0.5 text-sm font-semibold text-ink">{value}</div>
    </div>
  );
}

export function FundamentalsGrid({ data }: { data: Fundamentals }) {
  const cells: [string, string][] = [
    ['P/E', formatNumber(data.pe, 1)],
    ['P/B', formatNumber(data.pb, 1)],
    ['ROE', formatPct(data.roe_pct, { signed: false })],
    ['Debt / equity', formatNumber(data.debt_to_equity, 1)],
    ['Market cap', formatCrore(data.market_cap)],
    ['Operating margin', formatPct(data.operating_margin_pct, { signed: false })],
    ['Revenue YoY', formatPct(data.revenue_yoy_pct)],
    ['Profit YoY', formatPct(data.profit_yoy_pct)],
    ['EPS YoY', formatPct(data.eps_yoy_pct)],
    ['Operating cash flow', formatCrore(data.latest_ocf)],
    ['Sector', data.sector ?? DASH],
    ['Industry', data.industry ?? DASH],
  ];
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
      {cells.map(([label, value]) => (
        <Cell key={label} label={label} value={value} />
      ))}
    </div>
  );
}
