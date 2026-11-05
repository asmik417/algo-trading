import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pandas as pd
import streamlit as st

import config
from agents.emerging_explainer import explain
from data.nse_universe import build_market_panel, symbol_price_history
from scanner.emerging_scanner import run_scan
from scoring.buckets import market_cap_bucket, price_position_bucket

st.set_page_config(page_title="Emerging Opportunities", page_icon="🚀", layout="wide")

st.markdown("""
<style>
.eo-badge { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 0.85em; font-weight: 600; }
.eo-score { font-size: 2.2em; font-weight: 700; }
.eo-sub { color: #94a3b8; font-size: 0.85em; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 2px; }
.eo-positive { color: #4ade80; }
.eo-risk { color: #f87171; }
.eo-funnel { color: #64748b; font-size: 0.9em; }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_panel():
    return build_market_panel()


@st.cache_data(show_spinner=False)
def _cached_explain(symbol: str, score, _candidate):
    return explain(_candidate)


st.title("🚀 Emerging Opportunities")
st.caption("Stocks showing a combination of improving fundamentals, early price momentum and increasing market participation.")

with st.sidebar:
    st.title("⚙️ Scan Settings")
    shortlist_size = st.slider(
        "Stocks fully scored (Stage 2)", 20, 500, config.EMERGING_SHORTLIST_SIZE, step=20,
        help="Stage 1 cheaply screens the ENTIRE NSE universe for free using price/volume history. "
             "Only this many top survivors get real fundamentals pulled and fully scored.",
    )
    max_workers = st.slider("Parallel workers", 2, 10, 6)
    force_rescan = st.checkbox(
        "Force full rescan (ignore cache)", value=False,
        help="A scan is cached per trading day + shortlist size, so re-opening this page or clicking "
             "Scan Market again the same day is instant. Check this to fetch fresh fundamentals anyway.",
    )
    run_btn = st.button("🔍 Scan Market", type="primary", use_container_width=True)
    st.divider()
    st.caption("**Data sources**")
    st.caption("Price / volume — NSE bhavcopy (free, full market, all ~2,600 listed equities)")
    st.caption("Fundamentals — yfinance (shortlist only)")
    st.caption("Explanations — LLM narration of already-computed numbers, never the source of the score")

if run_btn:
    progress_bar = st.progress(0.0, text="Building full-market panel from NSE bhavcopy...")

    def _progress(done, total, sym):
        progress_bar.progress(done / total, text=f"Scoring {sym} ({done}/{total})")

    result = run_scan(shortlist_size=shortlist_size, max_workers=max_workers,
                       progress_callback=_progress, use_cache=not force_rescan)
    progress_bar.empty()
    st.session_state["emerging_scan"] = result

result = st.session_state.get("emerging_scan")

if result is None:
    st.info("Set scan settings in the sidebar and click **Scan Market** to screen the full NSE universe.")
    with st.expander("How this works", expanded=True):
        st.markdown("""
**Stage 1 — free, full market.** Every NSE-listed equity (~2,600 stocks) gets its price/volume history
built from NSE's own public daily bhavcopy archive — no subscription, no per-stock API calls — and is
cheaply ranked on how "early" its chart looks: not already extended, some volume pickup, still consolidating.

**Stage 2 — fundamentals, shortlist only.** Only the top-ranked survivors from Stage 1 get fundamentals,
quarterly results and cash flow pulled (via yfinance) and the full 6-pillar score computed.

**The score rewards:** earnings *acceleration* (profit outpacing revenue — a change in trajectory, not
just growth), fundamental quality, a stock whose price **hasn't already caught up** to the improved
fundamentals, rising volume/participation, a constructive technical setup, and reasonable valuation.

A stock that already rallied hard scores **lower** here, even with identical fundamentals — this finds
setups early, it does not rank the biggest recent gainers.
        """)
    st.stop()

candidates = result.candidates

st.markdown(
    f'<span class="eo-funnel">Screened <b>{result.universe_size:,}</b> NSE-listed equities '
    f'(as of {result.latest_trading_day}) → <b>{result.prefiltered_size}</b> passed the technical/volume '
    f'prefilter → <b>{result.scored_size}</b> had usable fundamentals and were fully scored.</span>',
    unsafe_allow_html=True,
)

# ── Summary cards ────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
strong = [c for c in candidates if c.total_score and c.total_score >= 70]
breakouts = [c for c in candidates if c.stage in ("Breakout", "Momentum")]
early = [c for c in candidates if "Early Setup" in c.signal]
avg_score = sum(c.total_score for c in candidates if c.total_score) / len(candidates) if candidates else 0
c1.metric("Candidates Found", len(candidates))
c2.metric("Strong Setups (70+)", len(strong))
c3.metric("Breakouts", len(breakouts))
c4.metric("Early Setups", len(early))
c5.metric("Avg Opportunity Score", f"{avg_score:.0f}")

st.divider()

if not candidates:
    st.warning("No candidates survived scoring this run — try increasing the Stage 2 shortlist size in the sidebar.")
    st.stop()

# ── Filters ───────────────────────────────────────────────────────────────────
f1, f2, f3, f4 = st.columns(4)
with f1:
    score_min = st.selectbox("Opportunity Score", ["All", "80+", "70+", "60+"], index=0)
with f2:
    stage_filter = st.multiselect("Stage", sorted({c.stage for c in candidates}))
with f3:
    signal_filter = st.multiselect("Signal", sorted({c.signal for c in candidates}))
with f4:
    cap_filter = st.multiselect("Market Cap", sorted({market_cap_bucket(c.market_cap) for c in candidates}))

f5, f6, f7 = st.columns(3)
with f5:
    growth_min = st.selectbox("Profit Growth (YoY)", ["All", ">20%", ">50%", ">100%"], index=0)
with f6:
    position_filter = st.multiselect("Price Position", sorted({price_position_bucket(c.stage) for c in candidates}))
with f7:
    sector_filter = st.multiselect("Sector", sorted({c.sector for c in candidates if c.sector}))

filtered = candidates
if score_min != "All":
    thresh = int(score_min.rstrip("+"))
    filtered = [c for c in filtered if c.total_score and c.total_score >= thresh]
if stage_filter:
    filtered = [c for c in filtered if c.stage in stage_filter]
if signal_filter:
    filtered = [c for c in filtered if c.signal in signal_filter]
if cap_filter:
    filtered = [c for c in filtered if market_cap_bucket(c.market_cap) in cap_filter]
if growth_min != "All":
    thresh = int(growth_min.lstrip(">").rstrip("%"))
    filtered = [c for c in filtered if c.profit_yoy_pct and c.profit_yoy_pct > thresh]
if position_filter:
    filtered = [c for c in filtered if price_position_bucket(c.stage) in position_filter]
if sector_filter:
    filtered = [c for c in filtered if c.sector in sector_filter]

filtered = sorted(filtered, key=lambda c: c.total_score or 0, reverse=True)
st.caption(f"Showing {len(filtered)} of {len(candidates)} candidates")


def _fmt_pct(v):
    return f"{v:+.0f}%" if v is not None else "—"


def _fmt_score(p):
    return f"{p.score:.0f}/{p.max_points}" if p.available and p.score is not None else "—"


# ── Table ─────────────────────────────────────────────────────────────────────
rows = []
for rank, c in enumerate(filtered, start=1):
    earn, pp, vol, tech, val = (c.pillars[k] for k in
                                 ("earnings_acceleration", "early_price_position", "volume_accumulation",
                                  "technical_setup", "valuation"))
    rows.append({
        "Rank": rank,
        "Stock": c.symbol,
        "Price": f"₹{c.current_price:,.1f}" if c.current_price else "—",
        "Score": round(c.total_score, 1) if c.total_score else None,
        "Signal": c.signal,
        "Stage": c.stage,
        "Revenue Growth": _fmt_pct(earn.details.get("revenue_yoy_pct")),
        "Profit Growth": _fmt_pct(earn.details.get("profit_yoy_pct")),
        "EPS Growth": _fmt_pct(earn.details.get("eps_yoy_pct")),
        "1M Return": _fmt_pct(pp.details.get("change_1m_pct")),
        "3M Return": _fmt_pct(pp.details.get("change_3m_pct")),
        "Volume vs Avg": f"{vol.details['volume_ratio_20d']:.1f}x" if vol.details.get("volume_ratio_20d") else "—",
        "Disconnect": pp.details.get("disconnect_label", "—"),
        "Valuation": _fmt_score(val),
        "Technical": _fmt_score(tech),
        "Risks": len(c.risks),
    })

df = pd.DataFrame(rows)
st.dataframe(
    df, use_container_width=True, hide_index=True, height=420,
    column_config={
        "Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%.0f"),
    },
)

st.divider()

# ── Detail view ───────────────────────────────────────────────────────────────
st.subheader("📋 Stock Research View")
symbol_options = [c.symbol for c in filtered]
if not symbol_options:
    st.info("No candidates match the current filters.")
    st.stop()

selected_symbol = st.selectbox("Select a stock for the full research view", symbol_options)
candidate = next(c for c in candidates if c.symbol == selected_symbol)

hc1, hc2, hc3 = st.columns([2, 1, 1])
with hc1:
    st.markdown(f"### {candidate.symbol}")
    st.caption(f"{candidate.sector or 'Sector unavailable'} · {market_cap_bucket(candidate.market_cap)}")
with hc2:
    st.markdown('<div class="eo-sub">Current Price</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="eo-score">₹{candidate.current_price:,.1f}</div>' if candidate.current_price else "—",
                unsafe_allow_html=True)
with hc3:
    st.markdown('<div class="eo-sub">Emerging Opportunity Score</div>', unsafe_allow_html=True)
    score_txt = f"{candidate.total_score:.0f} / 100" if candidate.total_score is not None else "—"
    st.markdown(f'<div class="eo-score">{score_txt}</div>', unsafe_allow_html=True)

bc1, bc2 = st.columns(2)
bc1.markdown(f"**Signal:** {candidate.signal}")
bc2.markdown(f"**Stage:** {candidate.stage}")

if candidate.data_coverage < 1.0:
    st.caption(f"⚠️ Data unavailable for {(1 - candidate.data_coverage) * 100:.0f}% of the pillar weighting — "
               f"score is renormalized over what could actually be computed, not padded with assumed zeros.")

# Why flagged / what changed
with st.spinner("Generating explanation...", show_time=False):
    try:
        narration = _cached_explain(candidate.symbol, candidate.total_score, candidate)
    except Exception:
        narration = {"why_flagged": "Explanation unavailable.", "what_changed": "Explanation unavailable."}

st.markdown("##### Why is this stock being flagged?")
st.info(narration.get("why_flagged", "—"))

st.markdown("##### What Changed?")
earn_d = candidate.pillars["earnings_acceleration"].details
wc1, wc2, wc3, wc4 = st.columns(4)
wc1.metric("Revenue Growth (YoY)", _fmt_pct(earn_d.get("revenue_yoy_pct")))
wc2.metric("Profit Growth (YoY)", _fmt_pct(earn_d.get("profit_yoy_pct")))
wc3.metric("EPS Growth (YoY)", _fmt_pct(earn_d.get("eps_yoy_pct")))
pp_d = candidate.pillars["early_price_position"].details
wc4.metric("3M Price Return", _fmt_pct(pp_d.get("change_3m_pct")))
st.caption(narration.get("what_changed", ""))

st.divider()

# Score breakdown
st.markdown("##### Score Breakdown")
weights = config.EMERGING_SCORE_WEIGHTS
pillar_labels = {
    "earnings_acceleration": "Earnings Acceleration",
    "fundamental_quality": "Fundamental Quality",
    "early_price_position": "Early Price Position",
    "volume_accumulation": "Volume / Accumulation",
    "technical_setup": "Technical Setup",
    "valuation": "Valuation",
}
for key, label in pillar_labels.items():
    p = candidate.pillars[key]
    col_a, col_b = st.columns([4, 1])
    with col_a:
        frac = (p.score / p.max_points) if (p.available and p.score is not None) else 0
        st.progress(min(max(frac, 0), 1), text=label)
    with col_b:
        st.markdown(_fmt_score(p) if p.available else "Data unavailable")

with st.expander("How is this score calculated?"):
    st.markdown(f"""
- **Earnings Acceleration ({weights['earnings_acceleration']} pts)** — rewards profit/EPS growth that
  outpaces revenue growth (margin expansion, not just volume) and rewards the growth *rate itself*
  accelerating quarter to quarter, not just high growth in isolation.
- **Fundamental Quality ({weights['fundamental_quality']} pts)** — ROE, operating/net margins, debt/equity,
  and whether free/operating cash flow is positive and improving.
- **Early Price Position ({weights['early_price_position']} pts)** — the Fundamental-Price Disconnect (how
  much of the fundamental improvement is *not yet* reflected in the price) plus a direct penalty for stocks
  that have already run up a lot, and a bonus for tight consolidation.
- **Volume / Accumulation ({weights['volume_accumulation']} pts)** — volume vs its 20-day average, how many
  of the last 10 sessions showed sustained (not one-off) elevated volume, and rising delivery %.
- **Technical Setup ({weights['technical_setup']} pts)** — the same RSI/MACD/EMA/Bollinger indicators used
  elsewhere in this app, scored for trend health and penalized for an overextended RSI.
- **Valuation ({weights['valuation']} pts)** — P/E relative to actual profit growth (PEG-style), a light
  absolute-P/E sanity check, and a penalty if the stock has already been re-rated over 6 months.

Any pillar that couldn't be computed (missing data) is **excluded**, not scored as zero — the total is
renormalized over the pillars that were actually available, and that coverage is shown above.
    """)

st.divider()

# Positives / Risks
pc1, pc2 = st.columns(2)
with pc1:
    st.markdown("##### ✅ Positive Signals")
    if candidate.positives:
        for pos in candidate.positives:
            st.markdown(f'<div class="eo-positive">• {pos}</div>', unsafe_allow_html=True)
    else:
        st.caption("None flagged.")
with pc2:
    st.markdown("##### ⚠️ Key Risks")
    if candidate.risks:
        for r in candidate.risks:
            st.markdown(f'<div class="eo-risk">• {r}</div>', unsafe_allow_html=True)
    else:
        st.caption("None flagged.")

st.divider()

# Price / volume timeline
st.markdown("##### Price & Volume Timeline")
panel = _cached_panel()
hist = symbol_price_history(panel, candidate.symbol)
if not hist.empty:
    tc1, tc2 = st.columns(2)
    with tc1:
        st.caption("Price (last 12 months)")
        st.line_chart(hist["Close"].tail(252))
    with tc2:
        st.caption("Volume (last 60 sessions)")
        st.bar_chart(hist["Volume"].tail(60))
    latest_q = earn_d.get("revenue_yoy_pct") is not None
    if latest_q:
        st.caption("Does the chart show fundamentals improving before price moved? Compare the volume pickup "
                    "above against the earnings numbers in \"What Changed\" — this scanner is built to flag "
                    "stocks where the earnings inflection came first.")
else:
    st.caption("Price history unavailable.")

st.divider()

# Historical validation
with st.expander("📊 Historical Validation"):
    st.markdown(
        "Historical validation unavailable — the current data providers (NSE bhavcopy for price/volume, "
        "yfinance for fundamentals) do not retain enough historical point-in-time quarterly fundamental data "
        "for Indian equities to run an honest, look-ahead-free backtest of this scanner. Rather than fabricate "
        "backtest statistics, this section is intentionally left blank until a data source with reliable "
        "historical fundamentals is integrated."
    )

st.divider()

# Watchlist
wl = st.session_state.setdefault("watchlist", list(config.WATCHLIST))
if candidate.symbol in wl:
    st.success(f"{candidate.symbol} is already in your watchlist (see the Stock Analysis tab).")
else:
    if st.button(f"➕ Add {candidate.symbol} to Watchlist", use_container_width=True):
        wl.append(candidate.symbol)
        st.session_state["watchlist"] = wl
        st.success(f"Added {candidate.symbol} to your watchlist.")
        st.rerun()
