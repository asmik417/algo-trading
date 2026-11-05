// The success metrics from docs/PRODUCT.md as tiles: win rate, P&L, averages, counts, how positions closed, extensions, reviews.
import { useNavigate } from 'react-router-dom';
import { pnlClass } from '../../lib/colors';
import { formatINR, formatNumber, formatPct } from '../../lib/format';
import type { ProfileStats } from '../../types/api';
import { Skeleton } from '../ui/Skeleton';
import { Stat } from '../ui/Stat';

export function StatsRow({
  stats,
  loading,
}: {
  stats: ProfileStats | undefined;
  loading: boolean;
}) {
  const navigate = useNavigate();
  if (loading || !stats) {
    return (
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {Array.from({ length: 8 }, (_, i) => (
          <Skeleton key={i} className="h-20" />
        ))}
      </div>
    );
  }
  const { closed_by: by, extensions: ext } = stats;
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <Stat
        label="Win rate"
        value={formatPct(stats.win_rate_pct, { signed: false })}
        sub={`${stats.wins} won · ${stats.losses} lost`}
      />
      <Stat
        label="Total paper P&L"
        value={formatINR(stats.total_pnl, { signed: true })}
        valueClassName={pnlClass(stats.total_pnl)}
        sub={`Realised ${formatINR(stats.realised_pnl, { signed: true })} · Unrealised ${formatINR(stats.unrealised_pnl, { signed: true })}`}
      />
      <Stat
        label="Avg gain / Avg loss"
        value={
          <>
            <span className={pnlClass(stats.avg_win_pct)}>{formatPct(stats.avg_win_pct)}</span>
            <span className="mx-1.5 text-ink-faint">/</span>
            <span className={pnlClass(stats.avg_loss_pct)}>{formatPct(stats.avg_loss_pct)}</span>
          </>
        }
        sub={`Average per closed trade ${formatPct(stats.avg_pnl_pct)}`}
      />
      <Stat
        label="Open · Due · Closed"
        value={`${stats.open} · ${stats.due} · ${stats.closed}`}
        sub={`${formatINR(stats.total_invested, { digits: 0 })} invested in total`}
      />
      <Stat
        label="How trades ended"
        value={`${by.target_hit} target · ${by.stop_hit} stop`}
        sub={`${by.horizon_closed} horizon expiry · ${by.manual} manual`}
      />
      <Stat
        label="Extensions"
        value={`${ext.helped} helped · ${ext.hurt} hurt`}
        sub={`${formatNumber(ext.count)} position${ext.count === 1 ? '' : 's'} extended`}
      />
      <Stat
        label="Pending reviews"
        value={stats.pending_reviews}
        valueClassName={stats.pending_reviews > 0 ? 'text-loss' : undefined}
        sub={stats.pending_reviews > 0 ? 'Open Loss Analysis →' : 'All losses reviewed'}
        onClick={() => navigate('/losses')}
      />
      <Stat
        label="Best · Worst"
        value={
          <>
            <span className="text-brand-dark">{stats.best ? stats.best.symbol : '—'}</span>
            <span className="mx-1.5 text-ink-faint">·</span>
            <span className="text-loss">{stats.worst ? stats.worst.symbol : '—'}</span>
          </>
        }
        sub={
          stats.best && stats.worst
            ? `${formatPct(stats.best.pnl_pct)} · ${formatPct(stats.worst.pnl_pct)}`
            : undefined
        }
      />
    </div>
  );
}
