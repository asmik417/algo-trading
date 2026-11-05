// Thin 0-100 bar with the number beside it (Score column).
import clsx from 'clsx';
import { formatNumber } from '../../lib/format';

export function ScoreBar({ score }: { score: number }) {
  const tone = score >= 70 ? 'bg-brand' : score >= 55 ? 'bg-amber-400' : 'bg-slate-400';
  return (
    <div className="flex items-center justify-end gap-2">
      <div
        className="h-1.5 w-16 overflow-hidden rounded-full bg-slate-100"
        role="img"
        aria-label={`Score ${score} out of 100`}
      >
        <div
          className={clsx('h-full rounded-full', tone)}
          style={{ width: `${Math.max(0, Math.min(100, score))}%` }}
        />
      </div>
      <span className="num w-9 text-right font-medium">{formatNumber(score, 1)}</span>
    </div>
  );
}
