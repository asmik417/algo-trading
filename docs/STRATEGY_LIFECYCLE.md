# Strategy Lifecycle

## Versioning model

Strategies are versioned, immutable after a run has started, and reproducible.

- `Strategy`: a named collection of parameters and risk configuration.
- `StrategyVersion`: immutable snapshot of the parameters, weights, and model config used in a run.
- `RunMetadata`: includes strategy version, data snapshot hash, risk config hash, code version, and seed.

## Promotion flow

1. Create or clone a strategy.
2. Adjust parameter values or risk settings.
3. Validate the parameters against the engine schema.
4. Save a new version.
5. Run a backtest or paper session against fixture data.
6. Compare the results to the benchmark and risk limits.
7. Promote the version when the results meet the reviewer criteria.

## Determinism contract

A given strategy version, data snapshot, risk config, and seed must produce the same run hash. This is required for auditability and replay.

## Guardrails

- No strategy mutation after a run starts.
- No future-data usage in signal generation.
- No order placement outside the paper broker.
