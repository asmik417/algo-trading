# AI Agent Guardrails

The platform supports AI guidance as an optional, advisory feature only. AI must never become a direct execution authority.

## Allowed behavior

- Explain signals and reasons in plain English.
- Tag loss reviews and suggest risk hypotheses.
- Review drift between backtest and paper results.
- Produce evidence-backed analysis, but store the exact evidence used.

## Forbidden behavior

- Placing orders.
- Changing risk limits or kill switches.
- Modifying strategy versions without human approval.
- Approving its own recommendations.
- Sending secrets or unrelated personal data to a model provider.

## Audit requirements

Each AI call must persist:

- model/provider name
- prompt version
- input hash
- output payload
- token or cost metadata, if available
- approval decision and approver

## Fail-closed behavior

If AI output is invalid, unavailable, or unapproved, the trading code path continues without using the AI result. No label can override a deterministic risk decision.
