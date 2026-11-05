// Circular score gauge for the dialog header.
import { formatNumber } from '../../lib/format';

export function ScoreRing({ score, size = 60 }: { score: number; size?: number }) {
  const stroke = 6;
  const r = (size - stroke) / 2;
  const circumference = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, score)) / 100;
  const color = score >= 70 ? '#00b386' : score >= 55 ? '#f59e0b' : '#94a3b8';
  return (
    <div
      className="relative shrink-0"
      style={{ width: size, height: size }}
      role="img"
      aria-label={`Score ${score} out of 100`}
    >
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="#e5e7eb"
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${circumference * pct} ${circumference}`}
        />
      </svg>
      <span className="num absolute inset-0 flex items-center justify-center text-sm font-semibold text-ink">
        {formatNumber(score, 0)}
      </span>
    </div>
  );
}
