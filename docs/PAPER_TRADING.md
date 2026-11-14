# Paper Trading Architecture

This project is intentionally paper-trading-first. No real order execution or brokerage integration is allowed in this phase. The core design principle is that all order logic, risk checks, fills, and portfolio reconciliation are deterministic and can be replayed with the same strategy version, data snapshot, and configuration.

## Execution model

- Strategy parameters live in the profile/strategy layer; they are versioned and immutable once used in a run.
- Signals are created from the pure scoring engine with a `strategy_version` and `as_of` timestamp.
- A signal becomes a paper order only after risk validation is passed.
- Fill logic is handled by the `PaperBroker` adapter, which consumes a market bar and applies conservative daily rules.
- Positions reconcile against cash and ledger entries using a deterministic ledger model.

## Key abstractions

- `Clock`: injects the current time for testability and replay.
- `MarketDataProvider`: provides historical bars without look-ahead bias.
- `CostModel`: estimates transaction and regulatory costs in rupees.
- `SlippageModel`: applies deterministic slippage for backtests and paper sessions.
- `PaperBroker`: a paper-only execution adapter which exposes `submit_order`, `cancel_order`, and `process_bar`.
- `PaperPortfolio`: owns cash and positions and enforces reconciliation invariants.

## Safety rules

1. No broker adapter may be used by default; the execution path is paper-only.
2. AI recommendations are advisory and are never allowed to place orders or override risk limits.
3. Risk limits are persisted and fail closed on validation errors.
4. All cash and position changes must be audit logged.

## Limitations

- This phase intentionally targets EOD/daily paper trading, not intraday live execution.
- Market data ingestion and replay remain test-fixture driven by default.
- The default cost model is a conservative approximation and should be refined with real operational assumptions later.
