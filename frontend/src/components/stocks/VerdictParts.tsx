// Small pieces that show a stock's verdict: Overall badge, Rules x/y, Chart label with a trend arrow.
import { ArrowDownRight, ArrowRight, ArrowUpRight } from 'lucide-react';
import { OVERALL_LABEL, OVERALL_TONE, TREND_WORD, rulesTone } from '../../lib/verdict';
import type { Trend, Verdict } from '../../types/api';
import { Badge } from '../ui/Badge';

export function OverallBadge({ verdict, large = false }: { verdict: Verdict; large?: boolean }) {
  return (
    <Badge
      tone={OVERALL_TONE[verdict.overall]}
      className={large ? 'px-3 py-1 text-sm font-semibold' : 'font-semibold'}
    >
      {OVERALL_LABEL[verdict.overall]}
    </Badge>
  );
}

export function TrendArrow({ trend }: { trend: Trend }) {
  const props = { className: 'h-4 w-4 shrink-0', 'aria-label': TREND_WORD[trend] };
  if (trend === 'uptrend')
    return <ArrowUpRight {...props} className={`${props.className} text-brand`} />;
  if (trend === 'downtrend')
    return <ArrowDownRight {...props} className={`${props.className} text-loss`} />;
  return <ArrowRight {...props} className={`${props.className} text-ink-muted`} />;
}

/** "6/9" coloured by how many rules failed; the failures are the tooltip. */
export function RulesBadge({ rules }: { rules: Verdict['rules'] }) {
  const tip = rules.failures.length
    ? rules.failures.join('\n')
    : 'Passes every rule that could be evaluated';
  return (
    <span title={tip} aria-label={`${rules.passed} of ${rules.total} rules pass. ${tip}`}>
      <Badge tone={rulesTone(rules)} className="num cursor-help">
        {rules.passed}/{rules.total}
      </Badge>
    </span>
  );
}

export function ChartLabel({ chart }: { chart: Verdict['chart'] }) {
  return (
    <span
      className="inline-flex items-center gap-1 whitespace-nowrap text-sm text-ink"
      title={chart.points.join(' · ')}
    >
      <TrendArrow trend={chart.trend} />
      {chart.label}
    </span>
  );
}
