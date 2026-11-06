# Backend tasks (today)

Work from `backend/`. Run tests after every step: `../venv/bin/python -m pytest tests -q`. Keep `docs/API_CONTRACT.md` open; the schemas must match it field for field.

State of play: the scoring engine already lives in `app/engine/` and its 10 tests pass. `app/engine/params.py` already defines `ScreenParams`, `DEFAULTS` and `PARAM_SPEC`. Nothing else exists yet.

## Step 0 — dependencies and app skeleton (30 min)
- Add to `requirements.txt`: `fastapi`, `uvicorn[standard]`, `sqlalchemy>=2.0`, `pydantic>=2`, `apscheduler>=3.10`, `httpx` (for tests). Install into `../venv`.
- `app/core/config.py`: `Settings` with `API_PREFIX="/api/v1"`, `CORS_ORIGINS=["http://localhost:4820"]`, `DATABASE_URL` (from `app.engine.config`), `DAILY_JOB_HOUR=18`, `DAILY_JOB_MINUTE=30`, `TZ="Asia/Kolkata"`.
- `app/db/base.py`, `app/db/session.py` (`get_db` dependency, `init_db()` calling `Base.metadata.create_all`).
- `app/main.py`: `create_app()`; CORS; include `api/v1/router.py`; `init_db()` on startup; leave a scheduler start hook for Step 10; `GET /api/v1/health`.
- Verify: `uvicorn app.main:app --port 8000` serves `/docs`.

## Step 1 — engine tweak: weights are an argument (10 min)
`app/engine/scoring/engine.py::evaluate` currently reads `config.EMERGING_SCORE_WEIGHTS`. Add `weights: dict | None = None`; use it when given, fall back to config. Add a test that different weights change `total_score`.

## Step 2 — models + schemas (45 min)
Implement every table in `docs/DATA_MODEL.md` under `app/models/`, and every response/request shape in `docs/API_CONTRACT.md` under `app/schemas/`. `Position` derived fields (`cash_left`, `current_value`, `days_held`, `days_to_exit`, `needs_review`) are computed in `tracker_service`, not stored.

## Step 3 — profiles (30 min)
`profile_service` + `api/v1/profiles.py`: CRUD, `activate`, `active`, `param-spec` (serialise `PARAM_SPEC`, `DEFAULTS`, `HORIZONS`, `CAP_BUCKETS`). Validation goes through `ScreenParams.validate()`; problems → 400. On first startup, if no profiles exist, seed one: name "Default – Balanced", owner "Roshan", defaults, active. Tests: create / update / activate / invalid weights.

## Step 4 — market data service (30 min)
`services/market_data.py`:
- `get_panel()` returns the bhavcopy panel (`engine.data.nse_universe.build_market_panel`), cached in process memory and rebuilt when the trading day changes (check `find_latest_trading_day()` first, it is cheap).
- `latest_trading_day()`, `history(symbol)` (via `symbol_price_history`), `latest_close(symbol)`, `close_on(symbol, date)` (last close on or before that date).
- `nifty_change_pct(from_date)` — fetch `^NSEI` via yfinance, cached per day; return `None` on failure.
Note: bhavcopy cache currently ends 2026-09-01; the first `get_panel()` will download ~45 missing days (a few minutes). Log progress.

## Step 5 — plan service (30 min)
`services/plan_service.build_plan(history, stage, params, trading_day) -> Plan` using `engine.data.indicators.compute_indicators`:
- `entry_aggressive = close`
- `entry_optimal = ema20 if ema20 < close else close - 0.5*atr`
- `entry_conservative = ema50 if ema50 < entry_optimal else close - 1.5*atr`
- `stop_loss = max(min(close - stop_atr_mult*atr, 0.98*low_20d), 0.80*close)`
- `risk = entry_aggressive - stop_loss`; `target = entry_aggressive + target_rr*risk`; `risk_reward = target_rr`
- Base horizon (trading days) by stage: Fundamental Change 60, Quiet Accumulation 50, Volume Expansion 35, Breakout 25, Momentum 20, Extended 10. Multiply by horizon preference: Short 0.6, Medium 1.0, Long 1.6. Clamp 10..130. `planned_exit_date = trading_day + horizon_days` business days (`numpy.busday_offset`).
- `timing_note` by stage (plain English, mention the actual rupee levels), `exit_note` with target, stop and exit date, fixed `disclaimer`.
Round prices to 2 decimals. Unit-test with synthetic history.

## Step 6 — suggestion service + runs (90 min) ← the core
`services/run_registry.py`: in-memory dict `run_id -> {status, progress}` plus a lock; one running run per profile.
`services/suggestion_service.run(profile_id, force_refetch=False)` executed in a `threading.Thread` from the router:
1. Create `SuggestionRun(status=queued)`; registry entry.
2. `panel = market_data.get_panel()`; phase `panel`.
3. Stage 1 prefilter: reuse `engine.scanner.emerging_scanner._stage1_prefilter` logic but apply `params.min_price` and `params.min_avg_turnover_lacs` (20-day mean of `turnover_lacs` from the panel). Take top `params.shortlist_size`. Phase `prefilter`.
4. Stage 2: for each symbol, load `{info, quarterly, cashflow}` from `data/cache/fundamentals/<trading_day>/<symbol>.pkl` or fetch via `engine.data.fetcher` and save. `ThreadPoolExecutor(max_workers=6)`. Phase `scoring`, progress per symbol. Call `evaluate(sym, hist, info, quarterly, cashflow, weights=params.weights)`. Skip when neither fundamental pillar is available (same rule as the old scanner).
5. Hard filters (phase `filtering`), each failure recorded as a human string: market-cap bucket in `allowed_caps`; `max_pe` (if > 0); `min_roe_pct`; `max_debt_to_equity` (if > 0); `min_profit_growth_pct`; `require_positive_ocf`; `rsi_min/max`; `require_above_200ema` (`ema_trend` in STRONG_UPTREND / ABOVE_200EMA); `max_3m_runup_pct`; `min_volume_ratio`; `score >= min_score`; signal not "Weak". Missing metric → filter is skipped (not failed).
6. Sort by score, keep `max_suggestions`, build plan for each (phase `planning`), persist (`saving`), update run counts, status `done`. Any exception → status `failed` with `error`.
Expose `analyze_symbol(symbol, profile_id)` that does steps 4-5 for one symbol and returns a `SuggestionDetail` with `filters.failures` (used by `/stocks/{symbol}/analyze`).
`services/analysis_service.build_detail(...)` assembles `SuggestionDetail`: score breakdown from `candidate.pillars` with weights, indicators, fundamentals (map yfinance keys: `trailingPE→pe`, `priceToBook→pb`, `returnOnEquity*100→roe_pct`, …), chart (last 130 rows with EMA20/50 series computed with `ta`), reasons. Narration: call `engine.agents.emerging_explainer.explain()` lazily on first detail request and cache in `narration_json`; if no OpenAI key, the deterministic fallback is fine.
Routers: `runs.py`, `suggestions.py`. Tests: run end-to-end against a tiny synthetic panel by monkeypatching `market_data.get_panel` and the fetcher (no network).

## Step 7 — explore (30 min)
`services/explore_service`: build `StockRow` for the whole universe from the panel in one vectorised pass (groupby symbol; `pct_change` over 1/5/21/63 rows; 252-row max for 52w high; 20-row volume mean; 20-row turnover mean). Cache the resulting DataFrame per trading day. Search, sort, paginate. `GET /stocks/{symbol}` detail with chart + indicators. Router `stocks.py` including `/analyze`.

## Step 8 — tracker (60 min)
`services/tracker_service`:
- `open_position(profile_id, suggestion_id|symbol, capital)`: entry = latest close; `qty = floor(capital/price)` (400 if 0); copy target/stop/exit date from the suggestion (or build a plan on the fly for a bare symbol using the profile params); event `open`; first mark.
- `mark_all(as_of_trading_day)`: for every `open`/`due` position: close price on that day → upsert mark, update `last_mark_date/last_close`; if `close <= stop_loss` → close `stop_hit`; elif `close >= target` → close `target_hit`; elif `mark_date >= planned_exit_date` and status open → status `due` + event `due`. Idempotent per day.
- `extend / shorten / close_manual / add_note` with validation per the contract; every one writes an event.
- `stats(profile_id)` per contract. `extensions.helped`: for each closed position with ≥1 extend event, compare final `pnl` with the mark on `original_exit_date` (or the last mark before it).
- `detail(position_id)` with marks, events, suggestion summary, benchmark via `market_data.nifty_change_pct`.
Router `positions.py` + `stats` on profiles. Tests with an in-memory SQLite and a fake price source.

## Step 9 — loss reviews (30 min)
`services/review_service`: tags list (keys + labels from `docs/DATA_MODEL.md`), pending = closed positions with `pnl < 0` and no review, create/update review, summary by tag. Router `reviews.py`.

## Step 10 — daily job + scheduler (30 min)
`app/jobs/daily_update.py::run_daily_update()`: refresh panel → `tracker_service.mark_all(latest_trading_day)` for all profiles → write `app_meta` (`last_daily_update`, `last_trading_day`, summary JSON). Guard with a lock so it never runs twice concurrently. `scripts/run_daily_update.py` calls it. APScheduler `BackgroundScheduler` cron Mon-Fri 18:30 Asia/Kolkata started in `main.py`. Router `jobs.py`.

## Step 11 — seed + smoke (20 min)
`scripts/seed_profiles.py` creates three profiles: "Roshan – Early Setups" (defaults), "Manager – Quality Large Caps" (`allowed_caps=[Large Cap]`, `min_roe_pct=15`, `max_pe=40`, `w_fundamental_quality=25`, `w_earnings_acceleration=20`, `w_technical_setup=10`), "MD – Momentum" (`rsi_min=50`, `rsi_max=80`, `max_3m_runup_pct=120`, `w_technical_setup=25`, `w_volume_accumulation=20`, `w_valuation=10`, horizon Short). Then start the server, `POST /profiles/1/runs`, poll until done, and paste the first three suggestions into your final message to the user.

## Definition of done
- Every endpoint in the contract responds with the documented shape (check in `/docs`).
- `pytest` green.
- A real run completes for the default profile and produces suggestions with plans.
- `backend/README.md` explains setup, run, test, and the daily job in under a page.
