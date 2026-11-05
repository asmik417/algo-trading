# Data model (SQLAlchemy, SQLite today)

All timestamps are ISO strings in UTC (`created_at`), all market dates are ISO `YYYY-MM-DD` trading days. Money is float rupees. Every table has an integer autoincrement `id` unless stated.

## profiles
| column | type | notes |
|---|---|---|
| name | str unique | e.g. "Roshan – Early Setups" |
| owner | str | free text: Roshan / Manager / MD |
| params_json | text | `ScreenParams.to_json()`; see `engine/params.py` for keys |
| is_active | bool | exactly one profile is active at a time (service enforces) |
| created_at, updated_at | str | |

## suggestion_runs
| column | type | notes |
|---|---|---|
| profile_id | FK profiles | cascade delete |
| trading_day | str | bhavcopy date the run was based on |
| status | str | queued, running, done, failed |
| universe_size, scored_size, passed_size | int | funnel counts |
| kind | str | `full` or `watchlist` |
| symbols_json | text nullable | requested symbols for a watchlist run |
| item_errors_json | text nullable | `{symbol: error}` for symbols that produced no suggestion row |
| params_json | text | snapshot of the params used |
| error | text nullable | |
| started_at, finished_at, created_at | str | |

## suggestions
| column | type | notes |
|---|---|---|
| run_id | FK suggestion_runs nullable | cascade; null for ad-hoc Explore analyses |
| source | str | `run` or `explore` |
| profile_id | FK profiles | denormalised for fast queries |
| symbol | str | NSE symbol, e.g. `RELIANCE` |
| trading_day | str | |
| rank | int | 1 = best |
| score | float | 0-100 |
| stage, signal | str | |
| price | float | close on trading_day |
| entry_aggressive, entry_optimal, entry_conservative | float | |
| stop_loss, target, risk_reward | float | |
| horizon_days | int | trading days |
| planned_exit_date | str | |
| timing_note, exit_note | text | plain-English plan notes (deterministic) |
| positives_json, risks_json | text | lists of strings |
| payload_json | text | full score breakdown + indicators + fundamentals (see API `score_breakdown`, `indicators`, `fundamentals`) |
| narration_json | text nullable | `{why_flagged, what_changed}` cached after first LLM call |
| created_at | str | |
Unique `(run_id, symbol)` where run_id is not null. Ad-hoc rows may repeat per symbol; `GET /profiles/{id}/suggestions` and the Suggested tab only read `source = run`.

## positions
| column | type | notes |
|---|---|---|
| profile_id | FK profiles | |
| suggestion_id | FK suggestions nullable | always set when opened through the UI (run or explore suggestion); null only for bare-symbol API calls |
| symbol | str | |
| opened_on | str | trading day of entry |
| entry_price | float | close on opened_on (paper fill) |
| qty | int | `floor(capital / entry_price)` |
| invested | float | `qty * entry_price` |
| capital | float | the profile's paper capital at open time |
| target, stop_loss | float nullable | copied from the suggestion plan |
| original_exit_date | str | never changes |
| planned_exit_date | str | changes on extend / shorten |
| status | str | open, due, closed |
| last_mark_date, last_close | nullable | updated by the daily job |
| closed_on, exit_price, pnl, pnl_pct, close_reason | nullable | `close_reason` ∈ target_hit, stop_hit, horizon_closed, manual |
| created_at | str | |

Derived (not stored): `cash_left = capital - invested`, `current_value = qty * last_close`, `days_held`, `days_to_exit`, `needs_review = status == closed and pnl < 0 and no loss_review`.

## position_events
| column | type | notes |
|---|---|---|
| position_id | FK positions | cascade |
| event_date | str | trading day |
| event_type | str | open, extend, shorten, due, close, note |
| old_exit_date, new_exit_date | str nullable | for extend / shorten |
| reason | text nullable | **required** for extend, shorten, manual close |
| price | float nullable | close on event_date |
| created_at | str | |

## position_marks
Primary key `(position_id, mark_date)`.
| column | type |
|---|---|
| close | float |
| value | float (`qty * close`) |
| pnl | float (`value - invested`) |
| pnl_pct | float |

## loss_reviews
| column | type | notes |
|---|---|---|
| position_id | FK positions unique | |
| reasons_json | text | list of tags from the fixed set below |
| mistakes, lesson, algo_change | text | free text |
| reviewed_on | str | |
| created_at | str | |

Fixed reason tags (`GET /api/v1/reviews/tags`):
`bought_extended`, `stop_too_tight`, `stop_too_wide`, `earnings_miss`, `whole_market_fell`, `sector_news`, `company_news`, `weak_fundamentals_missed`, `low_liquidity`, `held_too_long`, `exited_too_early`, `bad_entry_timing`, `other`.

## app_meta
Key/value: `last_daily_update` (ISO timestamp), `last_trading_day`, `panel_built_for` (trading day the in-memory panel was built from).

## Caches on disk (not in the DB)
- `data/cache/bhavcopy/<date>.csv` — one per trading day.
- `data/cache/fundamentals/<trading_day>/<symbol>.pkl` — `{info, quarterly, cashflow}` as fetched.
