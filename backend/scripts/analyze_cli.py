"""
AI Trade Assistant — CLI entry point.
Usage:
  python main.py                        # analyze default watchlist
  python main.py RELIANCE TCS INFY      # analyze specific stocks
  python main.py --capital 5000 SBIN    # set capital
"""
import json
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.engine import config
from app.engine.agents import technical_agent, fundamental_agent, sentiment_agent, consensus_agent, risk_agent
from app.engine.utils.logger import get_logger

log = get_logger("main")


def analyze_stock(symbol: str, capital: float) -> dict:
    log.info(f"Analyzing {symbol}...")
    tech = technical_agent.analyze(symbol)
    fund = fundamental_agent.analyze(symbol)
    sent = sentiment_agent.analyze(symbol)
    consensus = consensus_agent.build_consensus(symbol, tech, fund, sent)
    risk = risk_agent.calculate_risk(consensus, capital=capital)

    return {
        "symbol": symbol,
        "consensus": consensus,
        "risk": risk,
        "agents": {
            "technical": tech,
            "fundamental": fund,
            "sentiment": sent,
        },
    }


def print_result(result: dict):
    sym = result["symbol"]
    c = result["consensus"]
    r = result["risk"]

    signal = c.get("final_signal", "NEUTRAL")
    score = c.get("consensus_score", 50)
    votes = c.get("vote_breakdown", {})
    signal_icon = {"BUY": "BUY", "SELL": "SELL", "NEUTRAL": "---"}.get(signal, "---")

    print(f"\n{'='*60}")
    print(f"  {sym:15} | {signal_icon:4} | Score: {score:3}/100 | Votes B/S/N: {votes.get('BUY',0)}/{votes.get('SELL',0)}/{votes.get('NEUTRAL',0)}")
    print(f"{'='*60}")
    print(f"  Timeframe : {c.get('predicted_timeframe', 'N/A')}")
    print(f"  Entry     : {c.get('entry_strategy', 'N/A')}")
    print(f"  Exit      : {c.get('exit_strategy', 'N/A')}")
    print(f"  Reasoning : {c.get('overall_reasoning', 'N/A')}")
    print(f"  Watch For : {c.get('watch_for', 'N/A')}")
    print(f"  Risk      : Max ₹{r.get('max_risk_inr', 0)} | Target ₹{r.get('target_price', '?')} | Stop ₹{r.get('stop_loss_price', '?')} | R:R {r.get('risk_reward_ratio', '?')}")


def main():
    parser = argparse.ArgumentParser(description="AI Trade Assistant")
    parser.add_argument("symbols", nargs="*", help="Stock symbols (e.g. RELIANCE TCS)")
    parser.add_argument("--capital", type=float, default=config.DEFAULT_CAPITAL, help="Capital in INR")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    parser.add_argument("--workers", type=int, default=3, help="Parallel workers")
    args = parser.parse_args()

    symbols = [s.upper() for s in args.symbols] if args.symbols else config.WATCHLIST
    capital = args.capital

    print(f"\nAI Trade Assistant — analyzing {len(symbols)} stocks with ₹{capital:,.0f} capital")
    print(f"Model: {config.NARRATION_MODEL} | Stocks: {', '.join(symbols)}\n")

    results = []
    print(f"Scanning {len(symbols)} stocks... this takes ~2-3 minutes.\n")
    with ThreadPoolExecutor(max_workers=args.workers) as exe:
        futures = {exe.submit(analyze_stock, sym, capital): sym for sym in symbols}
        done = 0
        for future in as_completed(futures):
            sym = futures[future]
            done += 1
            try:
                result = future.result()
                results.append(result)
                score = result["consensus"].get("consensus_score", 50)
                sig = result["consensus"].get("final_signal", "NEUTRAL")
                print(f"  [{done:2}/{len(symbols)}] {sym:15} → {sig:7} (score {score}/100)")
            except Exception as e:
                log.error(f"Error analyzing {sym}: {e}")
                done_sym = sym
                print(f"  [{done:2}/{len(symbols)}] {sym:15} → ERROR")

    if args.json:
        print(json.dumps(results, indent=2, default=str))
        return

    # Rank: actionable first, then by consensus score descending
    actionable = [r for r in results if r["consensus"].get("action_recommended")]
    actionable.sort(key=lambda r: r["consensus"].get("consensus_score", 50), reverse=True)

    buys  = [r for r in actionable if r["consensus"].get("final_signal") == "BUY"]
    sells = [r for r in actionable if r["consensus"].get("final_signal") == "SELL"]

    print(f"\n\n{'#'*60}")
    print(f"  BEST SIGNALS TODAY  ({len(actionable)} out of {len(results)} stocks)")
    print(f"{'#'*60}")

    if buys:
        print(f"\n  ── TOP BUY OPPORTUNITIES ──")
        for r in buys:
            print_result(r)

    if sells:
        print(f"\n  ── TOP SELL / AVOID ──")
        for r in sells:
            print_result(r)

    if not buys and not sells:
        print("\n  No strong signals today. Patience is a position.")

    print(f"\n{'#'*60}")
    print(f"  Scanned: {len(results)} | Actionable: {len(actionable)} | BUY: {len(buys)} | SELL: {len(sells)}")
    print(f"{'#'*60}\n")


if __name__ == "__main__":
    main()
