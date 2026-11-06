"""Walk each pick forward with the Tracker's rules: entry, then on every later close stop -> target -> horizon,
costs, excursions, Nifty comparison; at most one open simulated trade per symbol.
"""
import math
from dataclasses import dataclass, field

import pandas as pd

from app.engine.backtest.history import after
from app.engine.backtest.replay import Pick

LIMIT_FILL_SESSIONS = 5           # optimal_limit: sessions after the scan date in which the limit may fill
CORPORATE_ACTION_MOVE = 0.40      # same threshold as the Tracker / suggestion filters

NO_FILL = "no_fill"
CORPORATE_ACTION = "corporate_action"


@dataclass
class Trade:
    symbol: str
    scan_date: str
    entry_date: str
    entry_price: float
    qty: int
    invested: float
    stop_loss: float
    target: float
    planned_exit_date: str
    signal: str
    stage: str
    score: float
    market_cap_bucket: str
    sector: str | None
    exit_date: str | None
    exit_price: float | None
    exit_reason: str              # target_hit | stop_hit | horizon_closed | open
    pnl: float
    pnl_pct: float
    r_multiple: float | None
    days_held: int
    mfe_pct: float | None
    mae_pct: float | None
    nifty_pct: float | None
    tags: list[str] = field(default_factory=list)
    avg_turnover_lacs: float | None = None   # at the scan date, for loss tagging (not part of the API shape)

    @property
    def closed(self) -> bool:
        return self.exit_reason != "open"


def _r2(x: float) -> float:
    return round(float(x), 2) + 0.0


def nifty_change_pct(nifty: pd.Series | None, start, end) -> float | None:
    """% change from the close on/before `start` to the close on/before `end`; None if either is missing."""
    if nifty is None or nifty.empty:
        return None
    a = nifty.loc[nifty.index <= pd.Timestamp(start)]
    b = nifty.loc[nifty.index <= pd.Timestamp(end)]
    if a.empty or b.empty or not a.iloc[-1]:
        return None
    return _r2((float(b.iloc[-1]) / float(a.iloc[-1]) - 1) * 100)


def simulate_pick(pick: Pick, history: pd.DataFrame, end_date, entry_rule: str, cost_pct: float, capital: float,
                  nifty: pd.Series | None = None) -> Trade | str:
    """A Trade, or NO_FILL / CORPORATE_ACTION. Only bars after the scan date (up to end_date) are used."""
    future = after(history, pick.scan_date, end_date)
    if future.empty:
        return NO_FILL
    if entry_rule == "next_close":
        entry_day, price = future.index[0], float(future["Close"].iloc[0])
    elif entry_rule == "optimal_limit":
        window = future.iloc[:LIMIT_FILL_SESSIONS]
        hits = window.index[window["Low"] <= pick.entry_optimal]
        if len(hits) == 0:
            return NO_FILL
        entry_day, price = hits[0], float(pick.entry_optimal)
    else:
        raise ValueError(f"unknown entry rule {entry_rule!r}")
    qty = math.floor(capital / price) if price > 0 else 0
    if qty < 1:
        return NO_FILL
    invested = qty * price

    held = future.loc[future.index > entry_day, "Close"]
    exit_day, exit_price, reason = None, None, "open"
    seen: list[float] = []
    prev = price
    for day, close in held.items():
        close = float(close)
        if prev and abs(close / prev - 1) > CORPORATE_ACTION_MOVE:
            return CORPORATE_ACTION  # unadjusted split/bonus while held: the P&L would be fiction
        prev = close
        seen.append(close)
        if close <= pick.stop_loss:
            exit_day, exit_price, reason = day, close, "stop_hit"
        elif close >= pick.target:
            exit_day, exit_price, reason = day, close, "target_hit"
        elif day >= pd.Timestamp(pick.planned_exit_date):
            exit_day, exit_price, reason = day, close, "horizon_closed"
        if reason != "open":
            break

    mark = exit_price if exit_price is not None else (seen[-1] if seen else price)
    last_day = exit_day if exit_day is not None else (held.index[len(seen) - 1] if seen else entry_day)
    pnl = qty * (mark - price) - invested * cost_pct / 100
    risk = price - pick.stop_loss
    return Trade(
        symbol=pick.symbol, scan_date=pick.scan_date.date().isoformat(), entry_date=entry_day.date().isoformat(),
        entry_price=_r2(price), qty=qty, invested=_r2(invested), stop_loss=pick.stop_loss, target=pick.target,
        planned_exit_date=pick.planned_exit_date, signal=pick.signal, stage=pick.stage, score=pick.score,
        market_cap_bucket=pick.market_cap_bucket, sector=pick.sector,
        exit_date=exit_day.date().isoformat() if exit_day is not None else None,
        exit_price=_r2(exit_price) if exit_price is not None else None, exit_reason=reason,
        pnl=_r2(pnl), pnl_pct=_r2(pnl / invested * 100), r_multiple=_r2((mark - price) / risk) if risk > 0 else None,
        days_held=len(seen), mfe_pct=_r2((max(seen) / price - 1) * 100) if seen else None,
        mae_pct=_r2((min(seen) / price - 1) * 100) if seen else None,
        nifty_pct=nifty_change_pct(nifty, entry_day, last_day), avg_turnover_lacs=pick.avg_turnover_lacs,
    )


@dataclass
class SimulationResult:
    trades: list[Trade]
    skipped_repeat: int = 0
    skipped_no_fill: int = 0
    dropped_corporate_action: int = 0


def simulate_all(picks_in_order: list[Pick], histories: dict[str, pd.DataFrame], end_date, entry_rule: str,
                 cost_pct: float, capital: float, nifty: pd.Series | None = None) -> SimulationResult:
    """Picks in scan-date order. A pick is skipped while the symbol's previous simulated trade is still open on
    the scan date (a trade that exits on the scan date has already freed the slot)."""
    result = SimulationResult(trades=[])
    busy_until: dict[str, pd.Timestamp | None] = {}  # symbol -> exit date of its latest trade (None = still open)
    for pick in sorted(picks_in_order, key=lambda p: (p.scan_date, p.rank)):
        if pick.symbol in busy_until:
            until = busy_until[pick.symbol]
            if until is None or until > pick.scan_date:
                result.skipped_repeat += 1
                continue
        outcome = simulate_pick(pick, histories[pick.symbol], end_date, entry_rule, cost_pct, capital, nifty)
        if outcome == NO_FILL:
            result.skipped_no_fill += 1
            continue
        if outcome == CORPORATE_ACTION:
            result.dropped_corporate_action += 1
            continue
        result.trades.append(outcome)
        busy_until[pick.symbol] = pd.Timestamp(outcome.exit_date) if outcome.exit_date else None
    return result
