// Mock of the deterministic Decision (contract section "Decision"): headline, findings, expectation, review rule,
// confidence and the narrative fallback, built only from numbers the stock already has.
import { formatDate, formatINR } from '../lib/format';
import type {
  ChartData,
  Confidence,
  Decision,
  Expectation,
  Finding,
  Fundamentals,
  Indicators,
  Plan,
  ReviewRule,
  SuggestionSummary,
} from '../types/api';
import { TRADING_DAY, round, shiftDays, weekdaysBetween } from './dates';

/** The trading day 20 sessions after the data day. */
export function twentySessionsOut(): string {
  return weekdaysBetween(shiftDays(TRADING_DAY, 1), shiftDays(TRADING_DAY, 40))[19];
}

/** "Profit grew…" → "profit grew…", but acronyms stay as they are ("RSI 77…", "P/E 95…", "ROE 8%…"). */
const lowerFirst = (t: string) =>
  /^[A-Z][A-Z/]/.test(t) ? t : t.charAt(0).toLowerCase() + t.slice(1);
const num = (v: number, d = 0) => String(round(v, d));

/** The fix for a failed rule, phrased as a condition ("unless <trigger>"). */
function fixFor(failure: string, s: SuggestionSummary, f: Fundamentals): string {
  let m: RegExpMatchArray | null;
  if ((m = failure.match(/^P\/E [\d.]+ above max ([\d.]+)/)) && f.pe)
    return `P/E falls under ${m[1]} (price below ${formatINR((s.price * Number(m[1])) / f.pe, { digits: 0 })})`;
  if ((m = failure.match(/^RSI [\d.]+ above max ([\d.]+)/))) return `RSI drops back under ${m[1]}`;
  if ((m = failure.match(/^RSI [\d.]+ below min ([\d.]+)/))) return `RSI recovers above ${m[1]}`;
  if ((m = failure.match(/^Profit growth .* below min (-?[\d.]+)%/)))
    return `the next quarterly results show profit growth of ${m[1]}% or more`;
  if (/^Volume /.test(failure)) return 'volume runs above 1.2× its average for 3 sessions';
  if ((m = failure.match(/^ROE .* below min ([\d.]+)%/)))
    return `the next results show ROE of ${m[1]}% or more`;
  if ((m = failure.match(/^Debt\/equity .* above max ([\d.]+)/)))
    return `debt/equity falls under ${m[1]}`;
  if (/^3-month run-up/.test(failure))
    return 'the price cools off and the 3-month run-up drops back under the limit';
  if ((m = failure.match(/^Score [\d.]+ below min ([\d.]+)/)))
    return `the score rises to ${m[1]} or more`;
  return 'the numbers behind this verdict change';
}

export function buildDecision(
  s: SuggestionSummary,
  plan: Plan,
  ind: Indicators,
  f: Fundamentals,
  chart: ChartData,
  confidence: Confidence,
): Decision {
  const v = s.verdict;
  const failures = v.rules.failures;
  const sym = s.symbol;

  // Against: the failed rules that drove the verdict (max 3), then negative chart points — each with its number.
  const against: Finding[] = failures.slice(0, 3).map((text) => ({ side: 'against', text }));
  if (ind.ema200 !== null && s.price < ind.ema200)
    against.push({
      side: 'against',
      text: `Price ${formatINR(s.price)} is below its 200-day EMA (${formatINR(ind.ema200)})`,
    });
  if (ind.rsi !== null && ind.rsi > 70)
    against.push({ side: 'against', text: `RSI at ${num(ind.rsi)}, above 70` });
  // Low volume is a chart point only when no volume rule already reported it.
  if (
    s.volume_ratio_20d !== null &&
    s.volume_ratio_20d < 0.8 &&
    !failures.some((x) => /^Volume /.test(x))
  )
    against.push({
      side: 'against',
      text: `Volume only ${s.volume_ratio_20d}× its 20-day average`,
    });
  if (ind.rsi !== null && ind.rsi < 40)
    against.push({ side: 'against', text: `RSI at ${num(ind.rsi)}, below 40` });
  if (
    s.change_3m_pct !== null &&
    s.change_3m_pct > 30 &&
    !failures.some((x) => /^3-month run-up/.test(x))
  )
    against.push({
      side: 'against',
      text: `Already up ${num(s.change_3m_pct, 1)}% in three months`,
    });

  // For: engine positives that carry a number.
  const forList: Finding[] = [];
  if (s.profit_yoy_pct !== null && s.profit_yoy_pct > 0)
    forList.push({ side: 'for', text: `Profit grew ${num(s.profit_yoy_pct)}% year on year` });
  if (
    f.pe !== null &&
    s.profit_yoy_pct !== null &&
    s.profit_yoy_pct > 0 &&
    f.pe / s.profit_yoy_pct < 1
  )
    forList.push({
      side: 'for',
      text: `PEG about ${num(f.pe / s.profit_yoy_pct, 2)} (P/E ${num(f.pe, 1)} against ${num(s.profit_yoy_pct)}% profit growth)`,
    });
  if (s.volume_ratio_20d !== null && s.volume_ratio_20d >= 1.3)
    forList.push({ side: 'for', text: `Volume ${s.volume_ratio_20d}× its 20-day average` });
  if (v.chart.trend === 'uptrend' && ind.ema200 !== null)
    forList.push({
      side: 'for',
      text: `Uptrend: price ${formatINR(s.price)} above its 200-day EMA (${formatINR(ind.ema200)})`,
    });
  if (f.operating_margin_pct !== null && f.operating_margin_pct >= 12)
    forList.push({ side: 'for', text: `Operating margin ${num(f.operating_margin_pct, 1)}%` });
  if (f.roe_pct !== null && f.roe_pct >= 15)
    forList.push({ side: 'for', text: `ROE ${num(f.roe_pct, 1)}%` });
  if (ind.rsi !== null && ind.rsi >= 40 && ind.rsi <= 70)
    forList.push({ side: 'for', text: `RSI ${num(ind.rsi)}, not overbought` });
  if (s.risk_reward >= 1.5)
    forList.push({ side: 'for', text: `Risk-reward ${s.risk_reward}:1 at the optimal entry` });

  const ordered = v.overall === 'buy' ? [...forList, ...against] : [...against, ...forList];
  const findings = ordered.slice(0, 6);

  const label = lowerFirst(v.chart.label);
  const firstFailure = failures[0] ?? null;
  const strongestFor = forList[0] ? lowerFirst(forList[0].text) : label;
  const headline =
    v.overall === 'buy'
      ? `Buy ${sym} near ${formatINR(s.entry_optimal, { digits: 0 })}: ${label}, ${strongestFor}.`
      : v.overall === 'watch'
        ? `Wait on ${sym}: ${firstFailure ? lowerFirst(firstFailure) : label}.`
        : `Avoid ${sym} for now: ${firstFailure ? lowerFirst(firstFailure) : 'the signal is weak'}; ${label}.`;

  // One condition feeds both the review rule and a Watch expectation ("becomes a Buy if … and <trigger>").
  const belowEma200 = ind.ema200 !== null && s.price < ind.ema200;
  const trigger =
    v.overall === 'buy'
      ? `it closes below the stop at ${formatINR(plan.stop_loss, { digits: 0 })}`
      : firstFailure
        ? fixFor(firstFailure, s, f)
        : s.signal.includes('Weak')
          ? 'the signal turns to Early Setup or Breakout'
          : belowEma200
            ? `it closes above the 200-day EMA (${formatINR(ind.ema200)})`
            : `it closes above its 20-day EMA (${formatINR(ind.ema20)})`;

  const in20 = twentySessionsOut();
  const low20 = Math.min(...chart.close.slice(-20));
  let expectation: Expectation;
  if (v.overall === 'buy') {
    expectation = {
      direction: 'up',
      level: plan.target,
      by_date: plan.planned_exit_date,
      text: `Expect ${formatINR(plan.target, { digits: 0 })} by ${formatDate(plan.planned_exit_date)} while it holds above ${formatINR(plan.stop_loss, { digits: 0 })}.`,
    };
  } else if (v.overall === 'watch') {
    const fix = trigger;
    expectation = {
      direction: 'sideways',
      level: s.entry_optimal,
      by_date: in20,
      text: `Expect a pullback toward ${formatINR(s.entry_optimal, { digits: 0 })}; becomes a Buy if it holds there and ${fix}.`,
    };
  } else if (v.chart.trend === 'downtrend') {
    const level = round(Math.max(plan.stop_loss, low20), 2);
    expectation = {
      direction: 'down',
      level,
      by_date: in20,
      text: `Expect further weakness toward ${formatINR(level, { digits: 0 })} over the next 4 weeks.`,
    };
  } else {
    expectation = {
      direction: 'sideways',
      level: null,
      by_date: in20,
      text: `The price may hold up, but the numbers do not support buying: ${firstFailure ? lowerFirst(firstFailure) : 'the signal is weak'}.`,
    };
  }

  const review: ReviewRule = { until: expectation.by_date, trigger };

  const narrative = [headline, ...findings.slice(0, 2).map((x) => `${x.text}.`)].join(' ');
  return { overall: v.overall, headline, findings, expectation, review, confidence, narrative };
}
