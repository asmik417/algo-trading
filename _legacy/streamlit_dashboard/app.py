import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

import config
from agents import technical_agent, fundamental_agent, sentiment_agent, consensus_agent, risk_agent

st.set_page_config(
    page_title="AI Trade Assistant",
    page_icon="📈",
    layout="wide",
)

st.markdown("""
<style>
.signal-buy  { color: #4ade80; font-weight: 700; font-size: 1.1em; }
.signal-sell { color: #f87171; font-weight: 700; font-size: 1.1em; }
.signal-neutral { color: #94a3b8; font-weight: 500; }
.score-high { color: #4ade80; font-weight: 600; }
.score-low  { color: #f87171; font-weight: 600; }
.entry-label { font-size: 0.75em; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; }
.price-val { font-size: 1.05em; font-weight: 600; }
.section-header { font-size: 0.8em; color: #64748b; text-transform: uppercase;
                  letter-spacing: 0.08em; margin-bottom: 4px; margin-top: 12px; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Settings")

    capital = st.number_input("Capital (₹)", min_value=100, max_value=1000000, value=1000, step=500)

    # Shared across pages via session_state, so symbols added from Emerging
    # Opportunities show up here too instead of a second, disconnected list.
    if "watchlist" not in st.session_state:
        st.session_state["watchlist"] = list(config.WATCHLIST)

    watchlist_input = st.text_area(
        "Watchlist (one per line)",
        value="\n".join(st.session_state["watchlist"]),
        height=300,
    )
    symbols = [s.strip().upper() for s in watchlist_input.strip().split("\n") if s.strip()]
    st.session_state["watchlist"] = symbols

    max_workers = st.slider("Parallel workers", 1, 5, 3)
    run_btn = st.button("🚀 Run Analysis", type="primary", use_container_width=True)

# ── Main ─────────────────────────────────────────────────────────────────────
st.title("📈 AI Trade Assistant")
st.caption(f"Multi-agent consensus system — scanning {len(symbols)} stocks")

if not run_btn:
    st.info("Set your capital and watchlist in the sidebar, then click **Run Analysis**.")
    with st.expander("How it works"):
        st.markdown("""
**3 independent AI agents analyze each stock:**
- **Technical** — RSI, MACD, Bollinger Bands, EMA trends → 3 entry price levels
- **Fundamental** — P/E, revenue growth, margins, debt
- **Sentiment** — Recent news headlines and market mood

**Consensus Agent** weighs all 3 → final signal + confidence score.

**Only stocks where ≥2 agents agree** appear as actionable — the rest are filtered out.
Click any stock row to see the full breakdown of what each agent found.
        """)
    st.stop()


# ── Analysis ─────────────────────────────────────────────────────────────────
def analyze_one(symbol: str) -> dict:
    tech = technical_agent.analyze(symbol)
    fund = fundamental_agent.analyze(symbol)
    sent = sentiment_agent.analyze(symbol)
    con  = consensus_agent.build_consensus(symbol, tech, fund, sent)
    risk = risk_agent.calculate_risk(con, capital=capital)
    return {
        "symbol": symbol,
        "consensus": con,
        "risk": risk,
        "agents": {"technical": tech, "fundamental": fund, "sentiment": sent},
    }


results = []
progress_bar = st.progress(0, text="Starting...")

with ThreadPoolExecutor(max_workers=max_workers) as exe:
    futures = {exe.submit(analyze_one, sym): sym for sym in symbols}
    done = 0
    for future in as_completed(futures):
        sym = futures[future]
        done += 1
        progress_bar.progress(done / len(symbols), text=f"Analyzed {sym} ({done}/{len(symbols)})")
        try:
            results.append(future.result())
        except Exception as e:
            st.warning(f"Error analyzing {sym}: {e}")

progress_bar.empty()

# ── Rank results ──────────────────────────────────────────────────────────────
actionable = [r for r in results if r["consensus"].get("action_recommended")]
skipped    = [r for r in results if not r["consensus"].get("action_recommended")]
actionable.sort(key=lambda r: r["consensus"].get("consensus_score", 50), reverse=True)

buys  = [r for r in actionable if r["consensus"].get("final_signal") == "BUY"]
sells = [r for r in actionable if r["consensus"].get("final_signal") == "SELL"]

# ── Top metrics ───────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("Stocks Scanned", len(results))
c2.metric("Actionable Signals", len(actionable))
c3.metric("BUY Signals", len(buys))
c4.metric("SELL / Avoid", len(sells))

st.divider()


# ── Helper to render one stock card ──────────────────────────────────────────
def render_stock(r: dict):
    sym  = r["symbol"]
    con  = r["consensus"]
    risk = r["risk"]
    tech = r["agents"]["technical"]
    fund = r["agents"]["fundamental"]
    sent = r["agents"]["sentiment"]
    ind  = tech.get("indicators", {})
    ad   = con.get("agent_details", {})
    tech_ad = ad.get("technical", {})

    signal = con.get("final_signal", "NEUTRAL")
    score  = con.get("consensus_score", 50)
    votes  = con.get("vote_breakdown", {})
    b_v    = votes.get("BUY", 0)
    s_v    = votes.get("SELL", 0)
    n_v    = votes.get("NEUTRAL", 0)

    e1 = tech_ad.get("entry_aggressive") or tech.get("entry_aggressive")
    e2 = tech_ad.get("entry_optimal")    or tech.get("entry_optimal")
    e3 = tech_ad.get("entry_conservative") or tech.get("entry_conservative")
    target    = risk.get("target_price")    or tech_ad.get("target") or tech.get("target_price")
    stop      = risk.get("stop_loss_price") or tech_ad.get("stop_loss") or tech.get("stop_loss")
    rr        = risk.get("risk_reward_ratio", "—")
    timeframe = con.get("predicted_timeframe", "—")

    def fmt(v):
        return f"₹{v:,.1f}" if isinstance(v, (int, float)) else "—"

    label = f"{'🟢' if signal == 'BUY' else ('🔴' if signal == 'SELL' else '⚪')}  {sym}  |  {signal}  |  Score {score}/100  |  Votes {b_v}B / {s_v}S / {n_v}N"

    with st.expander(label, expanded=False):

        # ── Row 1: entry prices ───────────────────────────────────────────
        st.markdown('<div class="section-header">Entry Prices — 3 levels (pick any, lower = safer)</div>', unsafe_allow_html=True)
        ec1, ec2, ec3 = st.columns(3)
        with ec1:
            st.markdown('<div class="entry-label">Entry 1 — Aggressive (now)</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="price-val">{fmt(e1)}</div>', unsafe_allow_html=True)
            st.caption("Enter immediately at market")
        with ec2:
            st.markdown('<div class="entry-label">Entry 2 — Optimal (pullback)</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="price-val">{fmt(e2)}</div>', unsafe_allow_html=True)
            st.caption("Best risk-reward entry")
        with ec3:
            st.markdown('<div class="entry-label">Entry 3 — Conservative (dip)</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="price-val">{fmt(e3)}</div>', unsafe_allow_html=True)
            st.caption("Deeper dip, higher conviction")

        st.divider()

        # ── Row 2: target / stop / hold ───────────────────────────────────
        st.markdown('<div class="section-header">Trade Plan</div>', unsafe_allow_html=True)
        tp1, tp2, tp3, tp4 = st.columns(4)
        tp1.metric("Target Exit", fmt(target), help="Price to book profit and exit")
        tp2.metric("Stop Loss",   fmt(stop),   help="Exit immediately if price hits this — protects your capital")
        tp3.metric("Risk:Reward", str(rr),     help="How much you gain vs risk per rupee")
        tp4.metric("Hold Period", timeframe,   help="Expected holding duration")

        st.caption(f"**Entry strategy:** {con.get('entry_strategy', '—')}")
        st.caption(f"**Exit strategy:** {con.get('exit_strategy', '—')}")
        st.caption(f"**Watch for:** {con.get('watch_for', '—')}")

        st.divider()

        # ── Row 3: agent breakdown ────────────────────────────────────────
        st.markdown('<div class="section-header">What Each Agent Found</div>', unsafe_allow_html=True)
        a1, a2, a3 = st.columns(3)

        with a1:
            t_sig = tech.get("signal", "—")
            t_con = tech.get("confidence", 0)
            st.markdown(f"**📊 Technical  ·  {t_sig} ({t_con}/5)**")
            st.write(f"RSI: **{ind.get('rsi', '—')}** → {ind.get('rsi_signal', '')}")
            st.write(f"MACD: {ind.get('macd_signal', '—')}")
            st.write(f"Trend: {ind.get('ema_trend', '—')}")
            st.write(f"Volume: {ind.get('volume_signal', '—')}")
            st.write(f"1W change: {ind.get('change_1w_pct', '—')}%  |  1M: {ind.get('change_1m_pct', '—')}%")
            st.caption(tech.get("reasoning", ""))

        with a2:
            f_sig = fund.get("signal", "—")
            f_con = fund.get("confidence", 0)
            raw   = fund.get("raw_data", {})
            st.markdown(f"**🏦 Fundamental  ·  {f_sig} ({f_con}/5)**")
            st.write(f"Valuation: **{fund.get('valuation', '—')}**")
            st.write(f"Growth: {fund.get('growth_outlook', '—')}")
            if raw.get("pe_ratio"):
                st.write(f"P/E: {raw['pe_ratio']:.1f}  |  P/B: {raw.get('pb_ratio', '—')}")
            if raw.get("profit_margins"):
                st.write(f"Margins: {raw['profit_margins']*100:.1f}%")
            if raw.get("debt_to_equity"):
                st.write(f"D/E: {raw['debt_to_equity']:.1f}")
            positives = fund.get("positives", [])
            red_flags = fund.get("red_flags", [])
            if positives:
                st.caption("✅ " + "  ·  ".join(positives[:2]))
            if red_flags:
                st.caption("⚠️ " + "  ·  ".join(red_flags[:2]))
            st.caption(fund.get("reasoning", ""))

        with a3:
            s_sig   = sent.get("signal", "—")
            s_con   = sent.get("confidence", 0)
            s_score = sent.get("sentiment_score", 50)
            st.markdown(f"**📰 Sentiment  ·  {s_sig} ({s_con}/5)**")
            st.write(f"Sentiment score: **{s_score}/100**")
            headlines = sent.get("key_headlines", [])
            if headlines:
                st.markdown("**Recent news:**")
                for h in headlines[:3]:
                    st.caption(f"• {h}")
            cats = sent.get("catalysts", {})
            if cats.get("bullish"):
                st.caption("🟢 " + " · ".join(cats["bullish"][:2]))
            if cats.get("bearish"):
                st.caption("🔴 " + " · ".join(cats["bearish"][:2]))
            st.caption(sent.get("reasoning", ""))

        st.divider()

        # ── Row 4: consensus reasoning ────────────────────────────────────
        st.markdown('<div class="section-header">Consensus Conclusion</div>', unsafe_allow_html=True)
        st.info(con.get("overall_reasoning", "—"))

        max_risk = risk.get("max_risk_inr", 0)
        st.caption(f"Max risk per trade with ₹{capital:,} capital: **₹{max_risk}** (1% rule)")


# ── Render BUY signals ────────────────────────────────────────────────────────
if buys:
    st.subheader("🟢 BUY Signals — ranked by confidence")
    for r in buys:
        render_stock(r)

if sells:
    st.subheader("🔴 SELL / Avoid — ranked by confidence")
    for r in sells:
        render_stock(r)

if not buys and not sells:
    st.warning("No strong signals today. All stocks show conflicted or neutral signals.")

# ── Skipped stocks (collapsed) ────────────────────────────────────────────────
if skipped:
    st.divider()
    with st.expander(f"⚪ {len(skipped)} stocks with no clear signal (skip these today)"):
        skip_rows = []
        for r in skipped:
            c  = r["consensus"]
            vt = c.get("vote_breakdown", {})
            skip_rows.append({
                "Symbol": r["symbol"],
                "Signal": c.get("final_signal", "NEUTRAL"),
                "Score":  c.get("consensus_score", 50),
                "Agreement": c.get("agreement_level", "—"),
                "Votes B/S/N": f"{vt.get('BUY',0)}/{vt.get('SELL',0)}/{vt.get('NEUTRAL',0)}",
            })
        st.dataframe(pd.DataFrame(skip_rows), use_container_width=True, hide_index=True)
