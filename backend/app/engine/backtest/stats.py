"""Backtest summary, breakdowns, loss-pattern shares, equity curve and drawdown.
Open-at-end trades count in `trades`, `exits.open` and total P&L (marked), never in win-rate maths.
"""
from collections import Counter, defaultdict
from collections.abc import Callable

from app.engine.backtest.simulate import Trade

EQUITY_BASE_MULTIPLE = 10  # drawdown is measured against capital_per_trade x 10


def _r2(x):
    return None if x is None else round(float(x), 2) + 0.0


def _mean(xs: list[float]) -> float | None:
    return _r2(sum(xs) / len(xs)) if xs else None


def equity_curve(trades: list[Trade]) -> list[dict]:
    """Cumulative closed P&L by exit date, one point per date."""
    by_day: dict[str, float] = defaultdict(float)
    for t in trades:
        if t.closed and t.exit_date:
            by_day[t.exit_date] += t.pnl
    points, running = [], 0.0
    for day in sorted(by_day):
        running += by_day[day]
        points.append({"date": day, "pnl": _r2(running)})
    return points


def max_drawdown_pct(curve: list[dict], capital_per_trade: float) -> float | None:
    """Largest peak-to-trough fall of the equity curve (peak starts at 0), as % of capital_per_trade x 10."""
    if not curve or capital_per_trade <= 0:
        return None
    peak, worst = 0.0, 0.0
    for point in curve:
        peak = max(peak, point["pnl"])
        worst = max(worst, peak - point["pnl"])
    return _r2(worst / (capital_per_trade * EQUITY_BASE_MULTIPLE) * 100)


def summary(trades: list[Trade], skipped_repeat: int, skipped_no_fill: int, capital_per_trade: float) -> dict:
    closed = [t for t in trades if t.closed]
    wins = [t for t in closed if t.pnl > 0]
    losses = [t for t in closed if t.pnl < 0]
    gross_win, gross_loss = sum(t.pnl for t in wins), -sum(t.pnl for t in losses)
    exits = Counter(t.exit_reason for t in trades)
    return {
        "trades": len(trades), "closed": len(closed), "wins": len(wins), "losses": len(losses),
        "open_at_end": exits.get("open", 0), "skipped_repeat": skipped_repeat, "skipped_no_fill": skipped_no_fill,
        "win_rate_pct": _r2(len(wins) / len(closed) * 100) if closed else None,
        "avg_win_pct": _mean([t.pnl_pct for t in wins]),
        "avg_loss_pct": _mean([t.pnl_pct for t in losses]),
        "avg_pnl_pct": _mean([t.pnl_pct for t in closed]),
        "expectancy_r": _mean([t.r_multiple for t in closed if t.r_multiple is not None]),
        "profit_factor": _r2(gross_win / gross_loss) if losses and gross_loss > 0 else None,
        "total_pnl": _r2(sum(t.pnl for t in trades)) or 0.0,
        "max_drawdown_pct": max_drawdown_pct(equity_curve(trades), capital_per_trade),
        "avg_days_held": _mean([t.days_held for t in closed]),
        "nifty_avg_pct": _mean([t.nifty_pct for t in closed if t.nifty_pct is not None]),
        "exits": {k: exits.get(k, 0) for k in ("target_hit", "stop_hit", "horizon_closed", "open")},
    }


def breakdown(trades: list[Trade], key: Callable[[Trade], str]) -> list[dict]:
    """Rows per key: trades (incl. open), win rate and average P&L % over closed trades, total P&L over all."""
    groups: dict[str, list[Trade]] = defaultdict(list)
    for t in trades:
        groups[key(t)].append(t)
    rows = []
    for k, ts in groups.items():
        closed = [t for t in ts if t.closed]
        wins = [t for t in closed if t.pnl > 0]
        rows.append({"key": k, "trades": len(ts),
                     "win_rate_pct": _r2(len(wins) / len(closed) * 100) if closed else None,
                     "avg_pnl_pct": _mean([t.pnl_pct for t in closed]), "total_pnl": _r2(sum(t.pnl for t in ts)) or 0.0})
    return sorted(rows, key=lambda r: (-r["trades"], r["key"]))


def breakdowns(trades: list[Trade]) -> dict:
    return {
        "by_signal": breakdown(trades, lambda t: t.signal),
        "by_stage": breakdown(trades, lambda t: t.stage),
        "by_market_cap": breakdown(trades, lambda t: t.market_cap_bucket),
        "by_sector": breakdown(trades, lambda t: t.sector or "Unknown"),
        "by_month": sorted(breakdown(trades, lambda t: t.entry_date[:7]), key=lambda r: r["key"]),
    }


def loss_patterns(trades: list[Trade], labels: dict[str, str]) -> list[dict]:
    """Tag counts over closed losing trades; share = count ÷ losing trades (tags overlap, so shares can sum > 100)."""
    losing = [t for t in trades if t.closed and t.pnl < 0]
    counts = Counter(tag for t in losing for tag in t.tags)
    order = list(labels)
    rows = [{"key": k, "label": labels.get(k, k), "count": n, "share_pct": _r2(n / len(losing) * 100)}
            for k, n in counts.items()]
    return sorted(rows, key=lambda r: (-r["count"], order.index(r["key"]) if r["key"] in order else len(order)))
