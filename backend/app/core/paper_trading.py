"""Paper-trading primitives: deterministic run hashing, order execution, and simple risk rules.
This is intentionally small and conservative: it is the first layer of a broader paper-trading
execution engine that will later evolve into strategy-versioned orders, fills, and audit trails.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Protocol

from app.core.clock import utc_now_iso


Money = Decimal
TWO_PLACES = Decimal("0.01")
ROUNDING = ROUND_HALF_UP


def to_money(value: Any) -> Money:
    return Decimal(str(value)).quantize(TWO_PLACES, rounding=ROUNDING)


@dataclass(frozen=True)
class RiskConfig:
    """Conservative defaults for paper-trading risk limits."""

    starting_capital: Money = to_money("100000")
    max_open_positions: int = 10
    max_position_weight: Money = to_money("0.15")
    max_sector_exposure: Money = to_money("0.30")
    max_daily_loss_pct: Money = to_money("0.05")
    per_trade_risk_pct: Money = to_money("0.01")
    allow_manual_override: bool = False
    kill_switch: bool = False


@dataclass(frozen=True)
class ExecutionPlan:
    symbol: str
    side: str
    quantity: int
    limit_price: Money | None = None
    stop_price: Money | None = None
    target_price: Money | None = None
    strategy_version: str = "unversioned"
    as_of: str = field(default_factory=utc_now_iso)
    reason: str = "paper_trade"
    mode: str = "paper-manual-approval"


@dataclass
class PaperOrder:
    order_id: str
    symbol: str
    side: str
    quantity: int
    order_type: str = "market"
    limit_price: Money | None = None
    stop_price: Money | None = None
    target_price: Money | None = None
    status: str = "pending"
    created_at: str = field(default_factory=utc_now_iso)
    filled_at: str | None = None
    filled_quantity: int = 0
    average_fill_price: Money | None = None
    rejection_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_filled(self) -> bool:
        return self.status == "filled"

    @property
    def remaining(self) -> int:
        return max(self.quantity - self.filled_quantity, 0)


@dataclass
class Fill:
    symbol: str
    quantity: int
    price: Money
    fees: Money
    slippage: Money
    timestamp: str = field(default_factory=utc_now_iso)


class CostModel:
    """Simplified cost model with conservative defaults for paper trading."""

    brokerage_rate: Money = to_money("0.0005")
    stt_rate: Money = to_money("0.00025")
    exchange_rate: Money = to_money("0.00004")
    sebi_rate: Money = to_money("0.000001")
    gst_rate: Money = to_money("0.18")
    stamp_duty_rate: Money = to_money("0.00003")
    dp_rate: Money = to_money("0.0002")

    def estimate(self, notional: Money) -> Money:
        brokerage = notional * self.brokerage_rate
        stt = notional * self.stt_rate
        exchange = notional * self.exchange_rate
        sebi = notional * self.sebi_rate
        gst = (brokerage + exchange + sebi) * self.gst_rate
        stamp_duty = notional * self.stamp_duty_rate
        dp = notional * self.dp_rate
        return to_money(brokerage + stt + exchange + sebi + gst + stamp_duty + dp)


class SlippageModel:
    """Small deterministic slippage applied to fills in a replayable paper run."""

    def __init__(self, bps: int = 15):
        self.bps = Decimal(bps)

    def apply(self, price: Money, side: str) -> Money:
        if side.lower() == "buy":
            return price * (Decimal("1") + (self.bps / Decimal("10000")))
        return price * (Decimal("1") - (self.bps / Decimal("10000")))


class BrokerPort(Protocol):
    def submit_order(self, order: PaperOrder) -> PaperOrder:
        ...

    def cancel_order(self, order_id: str) -> PaperOrder:
        ...

    def process_bar(self, symbol: str, close: Money, timestamp: str | None = None) -> list[PaperOrder]:
        ...


@dataclass
class PaperPortfolio:
    cash: Money = field(default_factory=lambda: to_money("100000"))
    positions: dict[str, int] = field(default_factory=dict)
    ledger: list[dict[str, Any]] = field(default_factory=list)

    def record(self, event: dict[str, Any]) -> None:
        self.ledger.append(event)

    def position_qty(self, symbol: str) -> int:
        return self.positions.get(symbol, 0)

    def add_fill(self, symbol: str, quantity: int, price: Money, fees: Money, side: str) -> None:
        notional = to_money(price * quantity)
        total_cash_impact = to_money(notional + fees)
        if side.lower() == "buy":
            self.cash -= total_cash_impact
        else:
            self.cash += to_money((price * quantity) - fees)
        current = self.positions.get(symbol, 0)
        self.positions[symbol] = current + (quantity if side.lower() == "buy" else -quantity)
        self.record({
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": str(price),
            "fees": str(fees),
            "cash_after": str(self.cash),
            "timestamp": utc_now_iso(),
        })

    def reconcile(self) -> bool:
        return self.cash >= Decimal("0") and all(qty >= 0 for qty in self.positions.values())


class PaperBroker(BrokerPort):
    """A simple paper broker intended for deterministic execution tests and replayable sessions."""

    def __init__(
        self,
        portfolio: PaperPortfolio | None = None,
        cost_model: CostModel | None = None,
        slippage_model: SlippageModel | None = None,
        risk_config: RiskConfig | None = None,
        market_prices: dict[str, Money] | None = None,
        execution_mode: str = "paper-manual-approval",
    ):
        self.portfolio = portfolio or PaperPortfolio()
        self.cost_model = cost_model or CostModel()
        self.slippage_model = slippage_model or SlippageModel()
        self.risk_config = risk_config or RiskConfig()
        self.market_prices = market_prices or {}
        self.execution_mode = execution_mode
        self.orders: dict[str, PaperOrder] = {}

    def _current_price(self, symbol: str) -> Money:
        return self.market_prices.get(symbol, to_money("0"))

    def _reject(self, order: PaperOrder, reason: str) -> PaperOrder:
        order.status = "rejected"
        order.rejection_reason = reason
        self.orders[order.order_id] = order
        return order

    def submit_order(self, order: PaperOrder) -> PaperOrder:
        if order.order_id in self.orders:
            return self._reject(order, "duplicate_order_id")
        if self.risk_config.kill_switch:
            return self._reject(order, "risk_kill_switch")
        if order.quantity <= 0:
            return self._reject(order, "non_positive_quantity")

        if order.side.lower() not in {"buy", "sell"}:
            return self._reject(order, "unsupported_side")

        available = self._current_price(order.symbol)
        if available <= 0:
            return self._reject(order, "missing_market_price")

        if self.execution_mode == "paper-manual-approval" and order.metadata.get("manual_approval") is not True:
            order.status = "pending_approval"
            self.orders[order.order_id] = order
            return order

        if self.risk_config.max_open_positions > 0:
            open_positions = len(self.portfolio.positions)
            if order.side.lower() == "buy" and open_positions >= self.risk_config.max_open_positions:
                return self._reject(order, "max_open_positions_reached")

        order.status = "filled"
        price = order.limit_price if order.limit_price is not None else available
        if order.side.lower() == "buy":
            price = self.slippage_model.apply(price, "buy")
        else:
            price = self.slippage_model.apply(price, "sell")

        notional = to_money(price * order.quantity)
        fees = self.cost_model.estimate(notional)
        if order.side.lower() == "buy" and self.portfolio.cash < (notional + fees):
            return self._reject(order, "insufficient_cash")

        self.portfolio.add_fill(order.symbol, order.quantity, price, fees, order.side)
        order.filled_at = utc_now_iso()
        order.filled_quantity = order.quantity
        order.average_fill_price = price
        self.orders[order.order_id] = order
        return order

    def cancel_order(self, order_id: str) -> PaperOrder:
        order = self.orders.get(order_id)
        if order is None:
            raise KeyError(f"Unknown order ID: {order_id}")
        order.status = "cancelled"
        return order

    def process_bar(self, symbol: str, close: Money, timestamp: str | None = None) -> list[PaperOrder]:
        """Applies obvious stop/target exit logic for existing paper orders.

        This is intentionally lightweight: the real engine will do richer portfolio event handling,
        but the public contract is stable and deterministic.
        """
        self.market_prices[symbol] = to_money(close)
        settled: list[PaperOrder] = []
        for order in self.orders.values():
            if order.symbol != symbol or order.status not in {"pending", "pending_approval"}:
                continue
            if order.stop_price is not None and order.side.lower() == "buy" and close <= order.stop_price:
                order.status = "filled"
                order.filled_at = timestamp or utc_now_iso()
                order.filled_quantity = order.quantity
                order.average_fill_price = order.stop_price
                settled.append(order)
            elif order.target_price is not None and order.side.lower() == "buy" and close >= order.target_price:
                order.status = "filled"
                order.filled_at = timestamp or utc_now_iso()
                order.filled_quantity = order.quantity
                order.average_fill_price = order.target_price
                settled.append(order)
        return settled


def build_run_hash(
    strategy_version: str,
    data_snapshot: str,
    config: dict[str, Any] | None,
    code_version: str,
    seed: str | int | None,
) -> str:
    """A stable hash for deterministic replayability across strategy/data/config changes."""
    payload = {
        "strategy_version": strategy_version,
        "data_snapshot": data_snapshot,
        "config": config or {},
        "code_version": code_version,
        "seed": str(seed or ""),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
