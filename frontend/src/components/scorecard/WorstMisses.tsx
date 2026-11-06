// The scorecard's worst misses: calls that went most against their direction at the chosen horizon.
// Each symbol opens the stock dialog.
import clsx from 'clsx';
import { ACTION_LABEL, ACTION_TONE } from '../../lib/brain';
import { pnlClass } from '../../lib/colors';
import { formatDate, formatINR, formatPct } from '../../lib/format';
import type { Direction, LoggedVerdict } from '../../types/api';
import { SignalBadge } from '../stocks/SignalBadge';
import { Badge } from '../ui/Badge';
import { Card } from '../ui/Card';

const DIRECTION_WORD: Record<Direction, string> = { up: 'up', down: 'down', sideways: 'sideways' };
const SOURCE_LABEL = { rules: 'Rules', analyst: 'Analyst' } as const;

export function WorstMisses({
  verdicts,
  horizon,
  onOpen,
}: {
  verdicts: LoggedVerdict[];
  horizon: 20 | 40 | 60;
  onOpen: (symbol: string) => void;
}) {
  return (
    <Card
      title="Worst misses"
      right={<span className="text-xs text-ink-muted">at {horizon} sessions</span>}
    >
      {verdicts.length === 0 ? (
        <p className="text-sm text-ink-muted">No wrong calls at {horizon} sessions yet.</p>
      ) : (
        <div className="-mx-4 -my-4 overflow-x-auto">
          <table className="min-w-full text-sm" aria-label="Worst misses">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-ink-muted">
              <tr>
                <th scope="col" className="px-4 py-2 text-left font-medium">
                  Symbol
                </th>
                <th scope="col" className="px-3 py-2 text-left font-medium">
                  Called on
                </th>
                <th scope="col" className="px-3 py-2 text-left font-medium">
                  Source
                </th>
                <th scope="col" className="px-3 py-2 text-left font-medium">
                  Signal
                </th>
                <th scope="col" className="px-3 py-2 text-left font-medium">
                  Call
                </th>
                <th scope="col" className="px-3 py-2 text-right font-medium">
                  Close then
                </th>
                <th scope="col" className="whitespace-nowrap px-3 py-2 text-right font-medium">
                  Close {horizon} sessions later
                </th>
                <th scope="col" className="px-3 py-2 text-right font-medium">
                  Change
                </th>
              </tr>
            </thead>
            <tbody>
              {verdicts.map((v) => {
                const mark = v.marks.find((m) => m.sessions === horizon);
                return (
                  <tr key={v.id} className="border-t border-line/70">
                    <td className="px-4 py-2">
                      <button
                        type="button"
                        onClick={() => onOpen(v.symbol)}
                        className="font-medium text-brand-dark hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-brand/40"
                      >
                        {v.symbol}
                      </button>
                    </td>
                    <td className="num whitespace-nowrap px-3 py-2 text-ink-muted">
                      {formatDate(v.day)}
                    </td>
                    <td className="px-3 py-2 text-ink">{SOURCE_LABEL[v.source]}</td>
                    <td className="whitespace-nowrap px-3 py-2">
                      {v.signal === null ? (
                        <span className="text-ink-muted">No signal</span>
                      ) : (
                        <SignalBadge signal={v.signal} />
                      )}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2">
                      <Badge tone={ACTION_TONE[v.action]}>{ACTION_LABEL[v.action]}</Badge>{' '}
                      <span className="text-xs text-ink-muted">
                        expected {DIRECTION_WORD[v.direction]}
                        {v.level !== null && (
                          <span className="num"> to {formatINR(v.level, { digits: 0 })}</span>
                        )}
                      </span>
                    </td>
                    <td className="num px-3 py-2 text-right">{formatINR(v.close)}</td>
                    <td className="num whitespace-nowrap px-3 py-2 text-right">
                      {formatINR(mark?.close)}
                      {mark && (
                        <span className="block text-xs text-ink-muted">
                          {formatDate(mark.date)}
                        </span>
                      )}
                    </td>
                    <td
                      className={clsx(
                        'num px-3 py-2 text-right font-medium',
                        pnlClass(mark?.change_pct),
                      )}
                    >
                      {formatPct(mark?.change_pct)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
