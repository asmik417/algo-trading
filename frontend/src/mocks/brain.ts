// Mock of "The brain": market briefs, evidence packs and analyst views (contract section "The brain").
// Pure builders plus small in-memory stores; db.ts wires them to the stock endpoints because it owns the stock data.
import type { Decision, Indicators, Plan, SuggestionSummary } from '../types/api';
import type {
  AnalystAction,
  AnalystView,
  EvidencePack,
  MarketBrief,
  MarketContext,
} from '../types/brain';
import { formatNumber } from '../lib/format';
import { NOW_ISO, TRADING_DAY, round, seeded, shiftDays, weekdaysBetween } from './dates';
import { fail } from './respond';

const PREV_DAY = weekdaysBetween(shiftDays(TRADING_DAY, -6), shiftDays(TRADING_DAY, -1)).slice(
  -1,
)[0];

/** The symbol whose analyst view does not exist until "Run analyst" is pressed. */
export const NO_VIEW_SYMBOL = 'CDSL';
/** The symbol whose stored view failed the number audit twice. */
export const UNAUDITED_SYMBOL = 'KALYANKJIL';
const ANALYST_DELAY_MS = 2500;

const CONTEXT: Record<string, MarketContext> = {
  [TRADING_DAY]: {
    day: TRADING_DAY,
    nifty_close: 24180.5,
    nifty_vs_ema50_pct: -1.8,
    nifty_1w_pct: -2.4,
    vix: 21.3,
    advance_decline: 0.62,
    fii_net_cr: -2840,
    dii_net_cr: 2210,
    sector_index: null,
    sector_1w_pct: null,
    sp500_1d_pct: -0.9,
    crude_1w_pct: 3.1,
    usdinr_1w_pct: 0.6,
  },
  [PREV_DAY]: {
    day: PREV_DAY,
    nifty_close: 24620.1,
    nifty_vs_ema50_pct: 0.4,
    nifty_1w_pct: -0.6,
    vix: 16.8,
    advance_decline: 1.04,
    fii_net_cr: -910,
    dii_net_cr: 1180,
    sector_index: null,
    sector_1w_pct: null,
    sp500_1d_pct: 0.3,
    crude_1w_pct: 1.2,
    usdinr_1w_pct: 0.2,
  },
};

const BRIEFS: MarketBrief[] = [
  {
    day: TRADING_DAY,
    regime: 'risk_off',
    context: CONTEXT[TRADING_DAY],
    leaders: [
      { index: 'NIFTY FMCG', change_1w_pct: 1.4 },
      { index: 'NIFTY PHARMA', change_1w_pct: 0.9 },
      { index: 'NIFTY IT', change_1w_pct: 0.3 },
    ],
    laggards: [
      { index: 'NIFTY SMALLCAP 100', change_1w_pct: -5.2 },
      { index: 'NIFTY METAL', change_1w_pct: -4.1 },
      { index: 'NIFTY REALTY', change_1w_pct: -3.8 },
    ],
    facts: [
      'Nifty 50 closed at 24,180.5, 1.8% below its 50-day EMA, and fell 2.4% this week.',
      'India VIX is 21.3, above 20.',
      'FIIs sold a net ₹2,840 cr today, the third session in a row above ₹2,000 cr; DIIs bought ₹2,210 cr.',
      'Advances to declines were 0.62: more stocks fell than rose.',
      'Small caps fell 5.2% this week, the weakest index; FMCG rose 1.4%, the strongest.',
    ],
    paragraph:
      'The market is under pressure: the Nifty is 1.8% below its 50-day average, volatility is above 20 and foreign investors have sold more than ₹2,000 cr for three sessions. Selling is broad, with small caps down 5.2% this week, while defensive FMCG and pharma held up.',
    stance: 'Small caps weak; do not add, hold winners with stops.',
    created_at: '2026-11-04T13:20:00Z',
  },
  {
    day: PREV_DAY,
    regime: 'neutral',
    context: CONTEXT[PREV_DAY],
    leaders: [
      { index: 'NIFTY BANK', change_1w_pct: 1.1 },
      { index: 'NIFTY AUTO', change_1w_pct: 0.8 },
    ],
    laggards: [
      { index: 'NIFTY METAL', change_1w_pct: -2.2 },
      { index: 'NIFTY MEDIA', change_1w_pct: -1.9 },
    ],
    facts: [
      'Nifty 50 closed at 24,620.1, 0.4% above its 50-day EMA, and slipped 0.6% this week.',
      'India VIX is 16.8, between 15 and 20.',
      'FIIs sold a net ₹910 cr; DIIs bought ₹1,180 cr.',
      'Advances to declines were 1.04.',
    ],
    paragraph:
      'A mixed session: the Nifty holds just above its 50-day average with volatility at 16.8. Foreign selling of ₹910 cr was absorbed by domestic buying. Banks led and metals lagged.',
    stance: 'Mixed tape; buy only the strongest setups, keep position sizes normal.',
    created_at: `${PREV_DAY}T13:20:00Z`,
  },
];

export function getMarketBrief(day?: string): MarketBrief {
  const b = day ? BRIEFS.find((x) => x.day === day) : BRIEFS[0];
  return b ?? fail(404, `No market brief for ${day}`);
}
export const listMarketBriefs = (limit = 10): MarketBrief[] => BRIEFS.slice(0, limit);

// ---------------------------------------------------------------- evidence packs

export interface PackInput {
  s: SuggestionSummary;
  ind: Indicators;
  plan: Plan | null;
  change1w: number | null;
  dist52w: number | null;
}

export function buildEvidencePack(
  { s, ind, plan, change1w, dist52w }: PackInput,
  day = TRADING_DAY,
): EvidencePack {
  const rand = seeded(`pack:${s.symbol}`);
  const profit = s.profit_yoy_pct;
  const baseRev = round(800 + rand() * 4000, 1);
  const quarters = ['Q2 FY27', 'Q1 FY27', 'Q4 FY26', 'Q3 FY26'].map((period, i) => {
    const revenue = round(baseRev * (1 - i * 0.04), 1);
    const margin = round(12 + rand() * 10, 1);
    const net = round(
      revenue * (margin / 100) * (profit !== null && profit < 0 ? 1 + i * 0.05 : 1 - i * 0.06),
      1,
    );
    return {
      period,
      filed_on: shiftDays(day, -20 - i * 91),
      revenue,
      ebitda: round((revenue * (margin + 6)) / 100, 1),
      net_profit: net,
      eps: round(net / 12, 2),
      margin_pct: margin,
    };
  });
  const noOwnership = rand() < 0.2;
  const deliveryNow = round(30 + rand() * 30, 0);
  const deliveryPrev = round(deliveryNow + (rand() - 0.6) * 20, 0);
  const unavailable = [
    ...(noOwnership ? ['ownership'] : []),
    ...(s.symbol.length % 3 === 0 ? ['headlines'] : []),
  ];
  return {
    symbol: s.symbol,
    day,
    price: {
      close: s.price,
      change_1w_pct: change1w,
      change_1m_pct: s.change_1m_pct,
      change_3m_pct: s.change_3m_pct,
      vs_nifty_1m_pct: s.change_1m_pct === null ? null : round(s.change_1m_pct + 1.9, 1),
      vs_sector_1m_pct: s.change_1m_pct === null ? null : round(s.change_1m_pct - rand() * 3, 1),
      dist_52w_high_pct: dist52w,
      volume_ratio: s.volume_ratio_20d,
      delivery_pct_now: deliveryNow,
      delivery_pct_prev: deliveryPrev,
      ema_trend: ind.ema_trend,
      rsi: ind.rsi,
    },
    quarters,
    ownership: noOwnership
      ? null
      : {
          as_of: '2026-09-30',
          promoter_pct: round(40 + rand() * 25, 2),
          promoter_change_pct: round((rand() - 0.5) * 2, 2),
          fii_pct: round(10 + rand() * 15, 2),
          dii_pct: round(8 + rand() * 12, 2),
          public_pct: round(10 + rand() * 10, 2),
          pledge_pct: rand() < 0.3 ? round(rand() * 8, 2) : 0,
        },
    deals:
      rand() < 0.5
        ? [
            {
              date: shiftDays(day, -3),
              kind: rand() < 0.5 ? 'bulk' : 'block',
              party: 'Mock Capital Fund',
              qty: Math.round(50000 + rand() * 400000),
              price: round(s.price * (0.97 + rand() * 0.04), 2),
            },
          ]
        : [],
    events: [
      { date: shiftDays(day, 9), kind: 'board_meeting', title: 'Board meeting: quarterly results' },
    ],
    headlines: unavailable.includes('headlines')
      ? []
      : [
          {
            date: shiftDays(day, -1),
            title: `${s.symbol} wins new order worth ₹${Math.round(100 + rand() * 900)} cr`,
            source: 'Mock Wire',
            url: `https://example.com/news/${s.symbol.toLowerCase()}-order`,
          },
          {
            date: shiftDays(day, -4),
            title: `${s.symbol}: analysts see margin pressure from input costs`,
            source: 'Mock Markets',
            url: `https://example.com/news/${s.symbol.toLowerCase()}-margins`,
          },
        ],
    market: CONTEXT[TRADING_DAY],
    rules_verdict: s.verdict,
    plan,
    unavailable,
  };
}

// Packs are deterministic, so only "is it built?" is state. NO_VIEW_SYMBOL starts unbuilt (GET 404 until POST).
const unbuilt = new Set<string>([NO_VIEW_SYMBOL]);
export const isPackBuilt = (symbol: string): boolean => !unbuilt.has(symbol);
export const markPackBuilt = (symbol: string): void => {
  unbuilt.delete(symbol);
};

// ---------------------------------------------------------------- analyst views

const views = new Map<string, AnalystView>();
const pending = new Map<string, number>(); // key -> time the queued view becomes ready
let nextViewId = 1;
const keyOf = (symbol: string, day: string, profileId: number) => `${symbol}:${day}:${profileId}`;

function agrees(action: AnalystAction, s: SuggestionSummary): boolean | null {
  const overall = s.verdict?.overall;
  if (!overall) return null;
  if (action === 'buy') return overall === 'buy';
  if (action === 'avoid' || action === 'exit') return overall === 'avoid';
  return false;
}

function composeView(
  s: SuggestionSummary,
  decision: Decision,
  pack: EvidencePack,
  profileId: number,
  audited: boolean,
): AnalystView {
  const rand = seeded(`view:${s.symbol}:${profileId}`);
  const p = pack.price;
  const deliveryFell =
    p.delivery_pct_now !== null &&
    p.delivery_pct_prev !== null &&
    p.delivery_pct_now < p.delivery_pct_prev;
  const rising = (p.change_1m_pct ?? 0) > 0;
  const anomalies = [
    ...(deliveryFell && rising
      ? [
          `Delivery % fell from ${p.delivery_pct_prev}% to ${p.delivery_pct_now}% while the price rose ${p.change_1m_pct}% in a month: buying may be short-term.`,
        ]
      : []),
    ...(pack.ownership?.pledge_pct
      ? [`Promoters have pledged ${pack.ownership.pledge_pct}% of their holding.`]
      : []),
  ];
  // The analyst usually follows the rules, but not always (that is what the scorecard measures).
  const flip = rand() < 0.25;
  const base: AnalystAction = decision.overall;
  const action: AnalystAction = flip
    ? base === 'buy'
      ? 'watch'
      : base === 'avoid'
        ? 'watch'
        : rand() < 0.5
          ? 'buy'
          : 'avoid'
    : base;
  const direction =
    action === 'buy'
      ? 'up'
      : action === 'avoid'
        ? s.verdict.chart.trend === 'downtrend'
          ? 'down'
          : 'sideways'
        : 'sideways';
  const q0 = pack.quarters[0];
  const fii = pack.market.fii_net_cr;
  return {
    id: nextViewId++,
    symbol: s.symbol,
    day: pack.day,
    profile_id: profileId,
    observations: [
      `Close ₹${p.close}, ${p.change_1m_pct ?? '—'}% over a month and ${p.change_3m_pct ?? '—'}% over three months.`,
      `Latest quarter (${q0.period}) net profit ₹${q0.net_profit} cr on revenue ₹${q0.revenue} cr, margin ${q0.margin_pct}%.`,
      `Nifty is ${pack.market.nifty_vs_ema50_pct}% from its 50-day EMA; VIX ${pack.market.vix}.`,
    ],
    anomalies,
    bull_case: `Revenue held at ₹${formatNumber(q0.revenue, 1)} cr with a ${q0.margin_pct}% margin, and volume runs ${p.volume_ratio ?? '—'}× its average: if the market steadies, ${s.symbol} can retest its 52-week high${p.dist_52w_high_pct === null ? '' : ` (it closed ${Math.abs(p.dist_52w_high_pct)}% below it)`}.`,
    bear_case: `The market is ${pack.market.vix !== null && pack.market.vix > 20 ? 'risk-off' : 'unsettled'} (VIX ${pack.market.vix ?? '—'}${fii === null ? '' : `, FIIs ${fii < 0 ? 'sold' : 'bought'} a net ₹${formatNumber(Math.abs(fii))} cr`}) and ${deliveryFell && rising ? 'the delivery data argues against conviction' : pack.ownership?.pledge_pct ? `promoters have pledged ${pack.ownership.pledge_pct}% of their holding` : `RSI is ${p.rsi ?? '—'}`}; a broad sell-off would take ${s.symbol} down with it.`,
    tests: [
      {
        claim: 'Buying is backed by delivery, not just trading volume',
        evidence: deliveryFell ? 'absent' : 'present',
        note: `Delivery ${p.delivery_pct_prev}% → ${p.delivery_pct_now}%`,
      },
      {
        claim: 'Profit growth is visible in the latest filing',
        evidence:
          s.profit_yoy_pct === null ? 'unknown' : s.profit_yoy_pct > 0 ? 'present' : 'absent',
        note:
          s.profit_yoy_pct === null
            ? 'No profit figure in the pack'
            : `Profit ${s.profit_yoy_pct}% YoY`,
      },
      {
        claim: 'No negative news in the last week',
        evidence: pack.headlines.length ? (rand() < 0.5 ? 'present' : 'absent') : 'unknown',
        note: pack.headlines.length
          ? `${pack.headlines.length} headlines checked`
          : 'Headlines unavailable',
      },
    ],
    action,
    direction,
    horizon_sessions: 20,
    confidence: flip ? 'low' : decision.overall === 'buy' ? 'high' : 'medium',
    trigger: decision.review.trigger,
    want_to_know: pack.ownership
      ? 'Whether the next results confirm the margin trend.'
      : 'The latest shareholding pattern (not in the pack).',
    agrees_with_rules: agrees(action, s),
    audited,
    audit_notes: audited
      ? []
      : [
          `"₹1,480 cr order book" not found in the evidence pack`,
          `"margin 26%" differs from the pack's ${q0.margin_pct}% by more than 1%`,
        ],
    model: 'claude-opus-5-5',
    created_at: NOW_ISO,
  };
}

/** The stored view for (symbol, day, profile), creating it for every fixture except NO_VIEW_SYMBOL. */
export function viewFor(
  s: SuggestionSummary,
  decision: Decision,
  pack: EvidencePack,
  profileId: number,
): AnalystView | null {
  const key = keyOf(s.symbol, pack.day, profileId);
  const queuedAt = pending.get(key);
  if (queuedAt !== undefined && Date.now() >= queuedAt) {
    pending.delete(key);
    views.set(key, composeView(s, decision, pack, profileId, true));
  }
  if (!views.has(key) && s.symbol !== NO_VIEW_SYMBOL)
    views.set(key, composeView(s, decision, pack, profileId, s.symbol !== UNAUDITED_SYMBOL));
  return views.get(key) ?? null;
}

/** POST analyst-view: the view if it exists, else queue one (ready after a short delay). */
export function requestView(
  s: SuggestionSummary,
  decision: Decision,
  pack: EvidencePack,
  profileId: number,
): { status: 'queued' } | AnalystView {
  const existing = viewFor(s, decision, pack, profileId);
  if (existing) return existing;
  const key = keyOf(s.symbol, pack.day, profileId);
  markPackBuilt(s.symbol); // the analyst reasons over a pack, so running it builds one
  if (!pending.has(key)) pending.set(key, Date.now() + ANALYST_DELAY_MS);
  return { status: 'queued' };
}
