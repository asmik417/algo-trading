// The evidence pack behind the analyst view (contract "The brain", EvidencePack), shown as the fourth Details row.
// Loaded only when the row is opened. Anything listed in `unavailable` is named, never filled in.
import { ExternalLink, PackageOpen } from 'lucide-react';
import { useBuildEvidence, useEvidence } from '../../hooks/useBrain';
import { unavailableLabel } from '../../lib/brain';
import { pnlClass } from '../../lib/colors';
import { formatDate, formatINR, formatMultiple, formatNumber, formatPct } from '../../lib/format';
import type { EvidencePack } from '../../types/api';
import { MarketContextTiles } from '../market/MarketContextTiles';
import { Button } from '../ui/Button';
import { ErrorNotice } from '../ui/ErrorNotice';
import { Skeleton } from '../ui/Skeleton';

const DEAL_KIND: Record<EvidencePack['deals'][number]['kind'], string> = {
  bulk: 'Bulk deal',
  block: 'Block deal',
  insider_buy: 'Insider buy',
  insider_sell: 'Insider sell',
};

function Heading({ children }: { children: string }) {
  return (
    <h4 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-ink-muted">
      {children}
    </h4>
  );
}

function Pairs({ rows }: { rows: { label: string; value: string; tone?: number | null }[] }) {
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm sm:grid-cols-3">
      {rows.map((r) => (
        <div key={r.label} className="flex justify-between gap-2 border-b border-line/60 py-1">
          <dt className="text-ink-muted">{r.label}</dt>
          <dd className={`num font-medium ${r.tone === undefined ? 'text-ink' : pnlClass(r.tone)}`}>
            {r.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}

const pct = (v: number | null) => formatPct(v, { signed: false, digits: 2 });

function PackBody({ pack: p }: { pack: EvidencePack }) {
  const pr = p.price;
  const o = p.ownership;
  return (
    <div className="space-y-5" data-testid="evidence-pack">
      <p className="text-xs text-ink-muted">
        Everything the analyst was given for {formatDate(p.day)}.{' '}
        {p.unavailable.length > 0 && (
          <span data-testid="evidence-unavailable">
            Unavailable:{' '}
            <strong className="font-medium text-ink">
              {p.unavailable.map(unavailableLabel).join(', ')}
            </strong>
            .
          </span>
        )}
      </p>

      <div>
        <Heading>Price</Heading>
        <Pairs
          rows={[
            { label: 'Close', value: formatINR(pr.close) },
            { label: '1 week', value: formatPct(pr.change_1w_pct), tone: pr.change_1w_pct },
            { label: '1 month', value: formatPct(pr.change_1m_pct), tone: pr.change_1m_pct },
            { label: '3 months', value: formatPct(pr.change_3m_pct), tone: pr.change_3m_pct },
            {
              label: 'vs Nifty, 1 month',
              value: formatPct(pr.vs_nifty_1m_pct),
              tone: pr.vs_nifty_1m_pct,
            },
            {
              label: 'vs sector, 1 month',
              value: formatPct(pr.vs_sector_1m_pct),
              tone: pr.vs_sector_1m_pct,
            },
            { label: 'From 52-week high', value: formatPct(pr.dist_52w_high_pct) },
            { label: 'Volume vs average', value: formatMultiple(pr.volume_ratio) },
            { label: 'Delivery now', value: pct(pr.delivery_pct_now) },
            { label: 'Delivery before', value: pct(pr.delivery_pct_prev) },
            { label: 'EMA trend', value: pr.ema_trend ?? '—' },
            { label: 'RSI', value: formatNumber(pr.rsi, 0) },
          ]}
        />
      </div>

      <div>
        <Heading>Quarterly results</Heading>
        {p.quarters.length === 0 ? (
          <p className="text-sm text-ink-muted">Unavailable</p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-line">
            <table className="min-w-full text-sm" aria-label="Quarterly results">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-ink-muted">
                <tr>
                  {[
                    'Quarter ended',
                    'Filed',
                    'Revenue (₹ cr)',
                    'EBITDA (₹ cr)',
                    'Net profit (₹ cr)',
                    'EPS (₹)',
                    'Margin',
                  ].map((h, i) => (
                    <th
                      key={h}
                      scope="col"
                      className={`px-3 py-2 font-medium ${i < 2 ? 'text-left' : 'text-right'}`}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {p.quarters.map((q) => (
                  <tr key={q.period} className="border-t border-line/70">
                    <td className="num whitespace-nowrap px-3 py-1.5 text-ink">
                      {formatDate(q.period)}
                    </td>
                    <td className="num whitespace-nowrap px-3 py-1.5 text-ink-muted">
                      {formatDate(q.filed_on)}
                    </td>
                    <td className="num px-3 py-1.5 text-right">{formatNumber(q.revenue, 1)}</td>
                    <td className="num px-3 py-1.5 text-right">{formatNumber(q.ebitda, 1)}</td>
                    <td className="num px-3 py-1.5 text-right">{formatNumber(q.net_profit, 1)}</td>
                    <td className="num px-3 py-1.5 text-right">{formatNumber(q.eps, 2)}</td>
                    <td className="num px-3 py-1.5 text-right">{pct(q.margin_pct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div>
        <Heading>Shareholding</Heading>
        {o === null ? (
          <p className="text-sm text-ink-muted">Unavailable</p>
        ) : (
          <>
            <Pairs
              rows={[
                { label: 'Promoters', value: pct(o.promoter_pct) },
                {
                  label: 'Promoter change',
                  value: formatPct(o.promoter_change_pct, { digits: 2 }),
                  tone: o.promoter_change_pct,
                },
                { label: 'Pledged', value: pct(o.pledge_pct) },
                { label: 'FIIs', value: pct(o.fii_pct) },
                { label: 'DIIs', value: pct(o.dii_pct) },
                { label: 'Public', value: pct(o.public_pct) },
              ]}
            />
            <p className="mt-1 text-xs text-ink-muted">As of {formatDate(o.as_of)}</p>
          </>
        )}
      </div>

      <div className="grid gap-5 md:grid-cols-2">
        <div>
          <Heading>Deals</Heading>
          {p.deals.length === 0 ? (
            <p className="text-sm text-ink-muted">No bulk, block or insider deals.</p>
          ) : (
            <ul className="space-y-1 text-sm text-ink">
              {p.deals.map((d) => (
                <li key={`${d.date}-${d.party}-${d.qty}`}>
                  <span className="num text-ink-muted">{formatDate(d.date)}</span> ·{' '}
                  {DEAL_KIND[d.kind]} · {d.party}:{' '}
                  <span className="num">{formatNumber(d.qty)}</span> shares
                  {d.price !== null && <span className="num"> at {formatINR(d.price)}</span>}
                </li>
              ))}
            </ul>
          )}
        </div>
        <div>
          <Heading>Upcoming events</Heading>
          {p.events.length === 0 ? (
            <p className="text-sm text-ink-muted">None announced.</p>
          ) : (
            <ul className="space-y-1 text-sm text-ink">
              {p.events.map((e) => (
                <li key={`${e.date}-${e.title}`}>
                  <span className="num text-ink-muted">{formatDate(e.date)}</span> · {e.title}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div>
        <Heading>Headlines</Heading>
        {p.headlines.length === 0 ? (
          <p className="text-sm text-ink-muted">
            {p.unavailable.includes('headlines') ? 'Unavailable' : 'No headlines this week.'}
          </p>
        ) : (
          <ul className="space-y-1 text-sm">
            {p.headlines.map((h) => (
              <li key={h.url}>
                <span className="num text-ink-muted">{formatDate(h.date)}</span> ·{' '}
                <a
                  href={h.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 font-medium text-brand-dark hover:underline"
                >
                  {h.title}
                  <ExternalLink className="h-3.5 w-3.5" aria-hidden />
                </a>{' '}
                <span className="text-ink-muted">({h.source})</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div>
        <Heading>Market</Heading>
        <MarketContextTiles context={p.market} />
      </div>
    </div>
  );
}

export function EvidencePackPanel({ symbol, day }: { symbol: string; day: string }) {
  const pack = useEvidence(symbol, day);
  const build = useBuildEvidence(symbol, day);
  if (pack.error) return <ErrorNotice error={pack.error} onRetry={() => void pack.refetch()} />;
  if (pack.isLoading) return <Skeleton className="h-32 w-full" />;
  if (!pack.data)
    return (
      <div className="space-y-2" data-testid="evidence-missing">
        <p className="flex items-center gap-2 text-sm text-ink-muted">
          <PackageOpen className="h-4 w-4" aria-hidden />
          No evidence pack for {symbol} on {formatDate(day)}. Packs are built nightly for pick
          lists, the algo&apos;s suggestions and open positions.
        </p>
        {build.error !== null && <ErrorNotice error={build.error} />}
        <Button
          size="sm"
          variant="secondary"
          loading={build.isPending}
          onClick={() => build.mutate()}
        >
          Build evidence pack
        </Button>
      </div>
    );
  return <PackBody pack={pack.data} />;
}
