// The market backdrop as small labelled tiles (contract "The brain", MarketContext). Missing values show "—".
import { formatINR, formatNumber, formatPct } from '../../lib/format';
import { pnlClass } from '../../lib/colors';
import type { MarketContext } from '../../types/api';

const crore = (v: number | null) =>
  v === null ? '—' : `${formatINR(v, { signed: true, digits: 0 })} cr`;

export function MarketContextTiles({ context: c }: { context: MarketContext }) {
  const tiles: { label: string; value: string; tone?: number | null }[] = [
    { label: 'Nifty 50', value: formatNumber(c.nifty_close, 1) },
    {
      label: 'Nifty vs 50-day EMA',
      value: formatPct(c.nifty_vs_ema50_pct),
      tone: c.nifty_vs_ema50_pct,
    },
    { label: 'Nifty 1 week', value: formatPct(c.nifty_1w_pct), tone: c.nifty_1w_pct },
    { label: 'India VIX', value: formatNumber(c.vix, 1) },
    { label: 'Advance / decline', value: formatNumber(c.advance_decline, 2) },
    { label: 'FII net', value: crore(c.fii_net_cr), tone: c.fii_net_cr },
    { label: 'DII net', value: crore(c.dii_net_cr), tone: c.dii_net_cr },
    ...(c.sector_index
      ? [
          {
            label: `${c.sector_index} 1 week`,
            value: formatPct(c.sector_1w_pct),
            tone: c.sector_1w_pct,
          },
        ]
      : []),
    { label: 'S&P 500 1 day', value: formatPct(c.sp500_1d_pct), tone: c.sp500_1d_pct },
    { label: 'Crude 1 week', value: formatPct(c.crude_1w_pct) },
    { label: 'USD/INR 1 week', value: formatPct(c.usdinr_1w_pct) },
  ];
  return (
    <dl
      className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4"
      data-testid="market-context"
    >
      {tiles.map((t) => (
        <div key={t.label} className="rounded-lg border border-line bg-white px-3 py-2">
          <dt className="text-xs text-ink-muted">{t.label}</dt>
          <dd
            className={`num mt-0.5 text-sm font-semibold ${t.tone === undefined ? 'text-ink' : pnlClass(t.tone)}`}
          >
            {t.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}
