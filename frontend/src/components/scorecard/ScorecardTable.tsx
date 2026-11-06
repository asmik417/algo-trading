// One breakdown of the scorecard (by source, action, signal or month): verdicts, marked, right, hit rate, average change.
import clsx from 'clsx';
import type { ReactNode } from 'react';
import { pnlClass } from '../../lib/colors';
import { formatNumber, formatPct } from '../../lib/format';
import type { ScorecardRow } from '../../types/api';
import { Card } from '../ui/Card';

export function ScorecardTable({
  title,
  keyHeader,
  rows,
  renderKey,
}: {
  title: string;
  keyHeader: string;
  rows: ScorecardRow[];
  renderKey: (key: string) => ReactNode;
}) {
  return (
    <Card title={title} className="min-w-0">
      {rows.length === 0 ? (
        <p className="text-sm text-ink-muted">Nothing logged.</p>
      ) : (
        <div className="-mx-4 -my-4 overflow-x-auto">
          <table className="min-w-full text-sm" aria-label={title}>
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-ink-muted">
              <tr>
                <th scope="col" className="px-4 py-2 text-left font-medium">
                  {keyHeader}
                </th>
                {['Verdicts', 'Marked', 'Right', 'Hit rate', 'Avg edge'].map((h) => (
                  <th
                    key={h}
                    scope="col"
                    className="whitespace-nowrap px-3 py-2 text-right font-medium"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.key} className="border-t border-line/70">
                  <td className="whitespace-nowrap px-4 py-2 text-ink">{renderKey(r.key)}</td>
                  <td className="num px-3 py-2 text-right">{formatNumber(r.verdicts)}</td>
                  <td className="num px-3 py-2 text-right">{formatNumber(r.marked)}</td>
                  <td className="num px-3 py-2 text-right">{formatNumber(r.right)}</td>
                  <td className="num px-3 py-2 text-right font-medium text-ink">
                    {formatPct(r.hit_rate_pct, { signed: false })}
                  </td>
                  <td className={clsx('num px-3 py-2 text-right', pnlClass(r.avg_change_pct))}>
                    {formatPct(r.avg_change_pct)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
