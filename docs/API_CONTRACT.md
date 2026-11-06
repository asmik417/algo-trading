# API contract — v1

Base URL: `http://localhost:8000/api/v1`. All bodies are JSON. Errors use `{"detail": "message"}` with 400 (bad input), 404 (missing), 409 (state conflict), 500.

Dates: ISO `YYYY-MM-DD`. Timestamps: ISO 8601 UTC. Money: rupees as numbers. Percentages are plain numbers (`12.5` means 12.5 %). `null` means unavailable, never 0.

Frontend copies the TypeScript types in the last section verbatim into `src/types/api.ts`.

---

## Health
`GET /health` → `{"status": "ok", "trading_day": "2026-11-04", "db": "ok"}`

---

## Auth (single user)

One login only. Credentials come from `backend/.env`: `APP_USERNAME`, `APP_PASSWORD`, `SECRET_KEY`. Every `/api/v1/*` route except `/health` and `/auth/*` returns 401 `{"detail": "Not authenticated"}` without a valid session cookie.

`POST /auth/login` body `{ "username": string, "password": string }` → `{ "username": "roshan" }` and sets an HttpOnly, SameSite=Lax cookie `session` (signed, 30-day expiry). Wrong credentials → 401.
`GET /auth/me` → `{ "username": "roshan" }` or 401.
`POST /auth/logout` → 204, clears the cookie.

```ts
export interface LoginBody { username: string; password: string; }
export interface Me { username: string; }
```

Frontend: axios `withCredentials: true`; any 401 redirects to `/login`; `/login` is the only route outside the app shell.

**Profiles are strategies, not users.** `owner` stays in the API for compatibility but the UI no longer shows or edits it (backend defaults it to the logged-in username). UI wording is "Strategy" wherever it said "Profile" or "Account"; the sidebar dropdown is "Active strategy"; the `/account` route becomes `/strategies`.

---

## Profiles (the "accounts")

`GET /profiles/param-spec` → the form definition for the Account page, straight from `engine/params.py`:
```json
{
  "defaults": { "min_price": 5, "...": "..." },
  "horizons": ["Short (2-6 weeks)", "Medium (1-3 months)", "Long (3-6 months)"],
  "cap_buckets": ["Large Cap", "Mid Cap", "Small Cap", "Unknown"],
  "sections": [
    { "section": "Universe", "help": "...", "fields": [
        { "key": "min_price", "label": "Minimum share price (₹)", "type": "number", "min": 1, "max": 5000, "step": 1, "help": "..." },
        { "key": "allowed_caps", "label": "Market cap buckets", "type": "multiselect", "options": ["Large Cap","Mid Cap","Small Cap","Unknown"] }
    ]}
  ]
}
```
Field `type` ∈ `number | int | bool | select | multiselect`.

**Scoring weights rule:** the six weight fields are always in the section named exactly `"Scoring weights"`, all `type: "int"`, keys `w_*`. They must total 100; otherwise `POST`/`PUT /profiles` returns 400 with `detail` naming the problem. Duplicate profile name → 409. Unknown param keys → 400. `PUT` merges partial `params` onto the saved ones.

`GET /profiles` → `Profile[]`
`POST /profiles` body `{ "name": string, "owner": string, "params"?: Params }` → `Profile` (201). Missing params keys take defaults. Validation errors → 400 with `detail` listing problems.
`GET /profiles/{id}` → `Profile`
`PUT /profiles/{id}` body `{ "name"?: string, "owner"?: string, "params"?: Params }` → `Profile`
`DELETE /profiles/{id}` → 204
`POST /profiles/{id}/activate` → `Profile` (sets `is_active` true on this one, false on all others)
`GET /profiles/active` → `Profile` or 404 when none.

```json
Profile = {
  "id": 1, "name": "Roshan – Early Setups", "owner": "Roshan", "is_active": true,
  "params": { ...all keys from param-spec defaults... },
  "params_summary": "score ≥ 60, top 15, Medium (1-3 months), P/E ≤ 60, ROE ≥ 10%, RSI 40-72",
  "created_at": "2026-11-05T09:00:00Z", "updated_at": "2026-11-05T09:00:00Z"
}
```

---

## Runs (executing the algo)

`POST /profiles/{id}/runs` body `{ "force_refetch"?: false }` → 202 `Run` with status `queued`. If a run for this profile is already `running`, return the existing one (200).
`GET /runs/{run_id}` → `Run`
`GET /profiles/{id}/runs?limit=10` → `Run[]` newest first.

```json
Run = {
  "id": 7, "profile_id": 1, "status": "running",          // queued | running | done | failed
  "trading_day": "2026-11-04",
  "progress": { "phase": "scoring", "done": 120, "total": 250, "current_symbol": "TATAELXSI" },
  // phase ∈ panel | prefilter | scoring | filtering | planning | saving | done
  "universe_size": 2612, "scored_size": 231, "passed_size": 14,
  "error": null, "started_at": "...", "finished_at": null, "created_at": "..."
}
```

---

## Watchlist runs (analyse a chosen list of stocks)

Same engine and same rules as a full run, but only for the symbols the user names. Results are persisted as suggestions with `source: "watchlist"` so they can be tracked, but they never appear in the Algo Suggested tab.

`POST /profiles/{id}/watchlist-runs` body `{ "list_id": 3 }` or `{ "symbols": ["RELIANCE", "TCS"] }` (see "Pick lists"; 1-50 symbols, upper-cased, unknown symbols reported, not fatal) → 202 `Run` with `kind: "watchlist"` and `symbols`.
`GET /runs/{run_id}/results` → `{ "run": Run, "items": WatchlistItem[] }` where items are in the order requested and include stocks that failed the filters.
`GET /profiles/{id}/watchlist-runs?limit=10` → `Run[]` newest first.

Rules: `GET /profiles/{id}/runs` returns **full runs only**; `run_id=latest` means the latest finished **full** run. Watchlist runs do not take the one-run-per-profile slot (they may run during a full run or alongside each other). `GET /runs/{id}/results` on a full run → 400. While a watchlist run is in progress, `results` lists only the symbols finished so far. For a watchlist run, `universe_size` = symbols requested, `scored_size` = analysed, `passed_size` = passed the filters.

```json
Run gains:   "kind": "full" | "watchlist",  "symbols": string[] | null
WatchlistItem = WatchlistHit | WatchlistMiss   // see the TS below; a miss carries exactly ten fields with filters null
```
`SuggestionSource` gains `"watchlist"`.

```ts
// WatchlistRunBody: see "Pick lists" (list_id or symbols, exactly one)
export interface WatchlistHit extends SuggestionSummary { filters: FilterResult; error: null; }
export interface WatchlistMiss { id: null; symbol: string; error: string; filters: null; score: null; signal: null; stage: null; price: null; is_tracked: false; position_id: null; }
export type WatchlistItem = WatchlistHit | WatchlistMiss;
export interface WatchlistResults { run: Run; items: WatchlistItem[]; }
```

---

## Pick lists (named, saved lists for My Picks)

A pick list is a named set of symbols the user keeps and re-analyses, e.g. "Manager holdings". Lists are **independent of strategies**: the same list can be analysed under any strategy. Names are unique (case-insensitive, trimmed), 1-60 chars. Symbols: 1-50, upper-cased, de-duplicated, order preserved.

`GET /pick-lists` → `PickList[]` ordered by `updated_at` desc.
`POST /pick-lists` body `{ "name": "Manager holdings", "symbols": ["HEGAM", "AMBER"] }` → 201 `PickList`. 409 on duplicate name.
`PUT /pick-lists/{id}` body `{ "name"?: string, "symbols"?: string[] }` (merge; rename and/or replace symbols) → `PickList`. 409 on duplicate name, 404 unknown id.
`DELETE /pick-lists/{id}` → 204. Past runs of that list are kept; their `list_id` becomes null.

Watchlist runs link to a list: `POST /profiles/{id}/watchlist-runs` body becomes `{ "list_id"?: number, "symbols"?: string[] }`. Exactly one of the two must be given (400 otherwise). With `list_id` the run uses the list's **current** symbols and stores `list_id`; the run's `symbols` is still filled so results stay readable after the list changes. `Run` gains `list_id: number | null` and `list_name: string | null` (name at read time; null if the list was deleted). `GET /profiles/{id}/watchlist-runs?limit=10&list_id=3` filters to one list; without `list_id` it returns all watchlist runs of the profile.

```ts
export interface WatchlistRunBody { list_id?: number; symbols?: string[]; }   // exactly one
```
`PickList`, `CreatePickListBody` and `UpdatePickListBody` are declared once in the main TS block.

Frontend behaviour (My Picks): a **list dropdown** shows every list by name, plus "New list…". The chosen list id is kept in `localStorage` (`picks.selectedListId`) so it stays selected across reloads until the user changes it. Selecting a list fills the symbol box with its symbols and shows the latest finished run of that list under the active strategy (`watchlist-runs?list_id=&limit=1`), or the empty state if none. Editing the symbols enables **Save list**; **Analyse** always saves first and then starts the run with `list_id`. The list name is editable inline (pencil next to the name → `PUT`). **Delete list** asks to confirm. The "Previous analyses" dropdown is scoped to the selected list. Analysing an ad-hoc set without saving is no longer offered; the user names the list first (default suggestion: "List <n>").

---

## Verdict (on every SuggestionSummary, SuggestionDetail and WatchlistHit)

Every analysed stock carries a three-part verdict so the UI never shows a bare "Fails".

```json
"verdict": {
  "overall": "buy" | "watch" | "avoid",
  "rules":  { "passed": 6, "total": 9, "failures": ["P/E 243 above max 50", "Profit growth -81% below min 20%"] },
  "chart":  { "trend": "uptrend" | "downtrend" | "sideways", "label": "Downtrend, weak", "points": ["Below 200-day EMA", "RSI 50", "Volume 1.5x"] },
  "reason": "Profit fell 81% YoY and price is below its 200-day average."
}
```
Rules: `total` counts only filters that could be evaluated (unavailable metrics are excluded, not failed). `chart.trend`: uptrend when ema_trend is STRONG_UPTREND / ABOVE_200EMA / UPTREND, downtrend when STRONG_DOWNTREND / BELOW_200EMA / DOWNTREND, else sideways. `chart.label` = trend word + ", " + stage or signal phrase (e.g. "Uptrend, breakout confirmed", "Sideways, quiet accumulation", "Downtrend, weak").
Overall: **avoid** if signal is Weak, or trend is downtrend, or profit growth YoY < 0, or more than 2 rule failures. **buy** if all rules pass and trend is uptrend and signal is Early Setup, Breakout Confirmed or Developing. Otherwise **watch**. `reason` is one deterministic sentence. With failures: "<first failure>; <chart label>." With no failures and overall buy/watch: "Passes all rules; <chart label>." With no failures and overall avoid: "Passes all rules, but the chart is <trend>: <chart label>." The LLM is not used here.

`Overall`, `Trend` and `Verdict` are declared once in the main TS block. `SuggestionSummary` gains `verdict: Verdict`. `filters` on SuggestionDetail / WatchlistHit stays for compatibility.

---

## Suggestions (Stocks → Algo Suggested)

`GET /profiles/{id}/suggestions?run_id=latest` → latest finished run for the profile and its items. `run_id` may be a number.
```json
{
  "run": Run | null,
  "items": SuggestionSummary[]
}
SuggestionSummary = {
  "id": 101, "source": "run", "symbol": "KPITTECH", "rank": 1, "score": 78.4,
  "stage": "Quiet Accumulation", "signal": "🟢 Early Setup",      // exact strings listed under "Enumerations"
  "price": 1234.5, "entry_optimal": 1210.0, "stop_loss": 1150.0, "target": 1400.0, "risk_reward": 2.0,
  "horizon_days": 50, "planned_exit_date": "2027-01-16",
  "market_cap_bucket": "Mid Cap", "sector": "Technology",
  "profit_yoy_pct": 42.1, "change_1m_pct": 3.2, "change_3m_pct": 11.0, "volume_ratio_20d": 1.6,
  "is_tracked": false, "position_id": null
}
```

`GET /suggestions/{id}` → `SuggestionDetail` (the dialog):
```json
SuggestionDetail = {
  ...SuggestionSummary,
  "trading_day": "2026-11-04",
  "reasons": {
    "why_flagged": "KPITTECH was flagged because ...",       // LLM narration of computed numbers, or deterministic fallback
    "what_changed": "Latest quarter profit grew 42% while the stock moved only 3%.",
    "positives": ["Profit growth (42%) is outpacing revenue growth (18%)."],
    "risks": ["RSI at 68 — approaching overbought."]
  },
  "plan": {
    "entry_aggressive": 1234.5, "entry_optimal": 1210.0, "entry_conservative": 1180.0,
    "stop_loss": 1150.0, "target": 1400.0, "risk_reward": 2.0,
    "horizon_days": 50, "planned_exit_date": "2027-01-16",
    "timing_note": "Accumulate on pullbacks toward ₹1,210 (20-day EMA) over the next 5-10 sessions; avoid chasing above ₹1,260.",
    "exit_note": "Book profit at ₹1,400 or exit on close below ₹1,150. Re-assess on 16 Jan 2027 if neither is hit.",
    "disclaimer": "This plan is rules-based and may vary with news and live market updates. Paper trading only."
  },
  "score_breakdown": [
    { "key": "earnings_acceleration", "label": "Earnings Acceleration", "score": 18.2, "max": 25, "weight": 25, "available": true,
      "details": { "revenue_yoy_pct": 18.0, "profit_yoy_pct": 42.1, "eps_yoy_pct": 40.0 } }
  ],
  "indicators": { "rsi": 61.2, "macd_signal": "BULLISH", "ema_trend": "STRONG_UPTREND", "ema20": 1210.0, "ema50": 1180.0, "ema200": 1050.0,
                  "atr": 28.4, "bb_position": "MID (62% from lower band)", "volume_ratio": 1.6 },
  "fundamentals": { "pe": 38.2, "pb": 7.1, "roe_pct": 24.0, "debt_to_equity": 12.0, "market_cap": 340000000000,
                    "sector": "Technology", "industry": "Software", "revenue_yoy_pct": 18.0, "profit_yoy_pct": 42.1, "eps_yoy_pct": 40.0,
                    "operating_margin_pct": 17.0, "latest_ocf": 5.2e9 },
  "chart": {
    "dates": ["2026-05-04", "..."], "close": [1100.2, "..."], "ema20": [null, "..."], "ema50": [null, "..."], "volume": [120000, "..."]
    // last ~130 trading days; nulls where an EMA is not yet defined
  },
  "filters": { "passed": true, "failures": [] }        // for /stocks/{symbol}/analyze: why it would not be suggested
}
```

---

## Stocks (Stocks → Explore)

`GET /stocks?search=&sort=change_1m_pct&order=desc&limit=50&offset=0` → full NSE equity universe from the latest bhavcopy panel.
```json
{ "trading_day": "2026-11-04", "total": 2612, "items": StockRow[] }
StockRow = {
  "symbol": "RELIANCE", "close": 2950.4, "change_1d_pct": 0.8, "change_1w_pct": -1.2, "change_1m_pct": 4.1, "change_3m_pct": 9.7,
  "dist_from_52w_high_pct": -3.5, "volume_ratio_20d": 1.1, "avg_turnover_lacs": 180000.0
}
```
`search` matches symbol prefix first, then substring, case-insensitive. Sortable keys: every numeric field plus `symbol`.

`GET /stocks/{symbol}` → `{ "symbol", "trading_day", "close", "metrics": StockRow, "indicators": {...same as detail...}, "chart": {...same as detail...} }`

`POST /stocks/{symbol}/analyze?profile_id=1` → `SuggestionDetail` with `source: "explore"` and a real `id`, scored on demand under that profile's parameters. `filters.passed=false` with `failures` like `["P/E 95 above max 60", "RSI 78 above max 72"]` when it would not be suggested. May take 5-15 s (one yfinance fetch); frontend shows a loading state. 404 if the symbol is not in the universe.

---

## Positions (Tracker)

`POST /positions` body `{ "profile_id": 1, "suggestion_id"?: 101, "symbol"?: "KPITTECH", "capital"?: 10000 }` → `Position` (201). One of `suggestion_id` / `symbol` is required. Entry price = close on the latest trading day. 409 if an open/due position already exists for that profile + symbol.
`GET /profiles/{id}/positions?status=open|due|closed|all` (default `all`) → `Position[]` newest first.
`GET /positions/{id}` → `PositionDetail`
`POST /positions/{id}/extend` body `{ "new_exit_date": "2027-02-15", "reason": "..." }` → `PositionDetail`. 400 if date ≤ current planned date or reason empty. Status `due` → `open`.
`POST /positions/{id}/shorten` body `{ "new_exit_date": "...", "reason": "..." }` → `PositionDetail`. 400 if date ≥ current planned date.
`POST /positions/{id}/close` body `{ "reason": "..." }` → `PositionDetail`. Closes at the latest close; `close_reason = manual`.
`POST /positions/{id}/notes` body `{ "note": "..." }` → `PositionDetail`
`GET /profiles/{id}/stats` → `ProfileStats`

```json
Position = {
  "id": 5, "profile_id": 1, "suggestion_id": 101, "symbol": "KPITTECH",
  "opened_on": "2026-11-04", "entry_price": 1234.5, "qty": 8, "invested": 9876.0, "capital": 10000, "cash_left": 124.0,
  "target": 1400.0, "stop_loss": 1150.0,
  "original_exit_date": "2027-01-16", "planned_exit_date": "2027-01-16",
  "status": "open",                                     // open | due | closed
  "last_mark_date": "2026-11-05", "last_close": 1250.0, "current_value": 10000.0, "pnl": 124.0, "pnl_pct": 1.26,
  "days_held": 1, "days_to_exit": 49,
  "closed_on": null, "exit_price": null, "close_reason": null,   // target_hit | stop_hit | horizon_closed | manual
  "needs_review": false, "stage": "Quiet Accumulation", "signal": "🟢 Early Setup"
}
PositionDetail = {
  ...Position,
  "marks": [ { "mark_date": "2026-11-05", "close": 1250.0, "value": 10000.0, "pnl": 124.0, "pnl_pct": 1.26 } ],
  "events": [ { "id": 1, "event_date": "2026-11-04", "event_type": "open", "old_exit_date": null, "new_exit_date": "2027-01-16",
                "reason": null, "price": 1234.5, "created_at": "..." } ],
  "suggestion": SuggestionSummary | null,
  "benchmark": { "symbol": "NIFTY 50", "change_pct_since_open": 2.1 } | null
}
ProfileStats = {
  "open": 6, "due": 1, "closed": 12, "wins": 7, "losses": 5, "win_rate_pct": 58.3,
  "avg_pnl_pct": 2.4, "avg_win_pct": 8.1, "avg_loss_pct": -5.6,
  "total_pnl": 2890.0, "realised_pnl": 2100.0, "unrealised_pnl": 790.0, "total_invested": 118000.0,   // total = all positions; realised = closed only; unrealised = open + due
  "best": { "symbol": "KPITTECH", "pnl_pct": 14.2 } | null, "worst": { "symbol": "X", "pnl_pct": -9.1 } | null,
  "closed_by": { "target_hit": 4, "stop_hit": 3, "horizon_closed": 3, "manual": 2 },
  "extensions": { "count": 3, "helped": 1, "hurt": 2 },
  "pending_reviews": 2
}
```
`extensions.helped` counts extended positions whose final P&L beat the P&L on the original exit date (from marks).

---

## Loss reviews (Loss Analysis)

`GET /reviews/tags` → `[{ "key": "bought_extended", "label": "Bought when already extended" }, ...]`
`GET /profiles/{id}/losses` → `{ "pending": Position[], "reviewed": Review[] }`
`POST /positions/{id}/review` body `{ "reasons": ["stop_too_tight","whole_market_fell"], "mistakes": "...", "lesson": "...", "algo_change": "..." }` → `Review` (201). 409 if the position is not a closed loss or already reviewed. `PUT /reviews/{id}` same body → `Review`.
`GET /profiles/{id}/losses/summary` → `{ "total_losses": 5, "reviewed": 3, "by_tag": [{ "key": "stop_too_tight", "label": "...", "count": 2 }], "avg_loss_pct": -5.6 }`

```json
Review = { "id": 3, "position_id": 9, "symbol": "X", "pnl": -560.0, "pnl_pct": -5.6, "closed_on": "...", "close_reason": "stop_hit",
           "reasons": ["stop_too_tight"], "mistakes": "...", "lesson": "...", "algo_change": "...", "reviewed_on": "2026-11-05", "created_at": "..." }
```

---

## Backtests (the time machine)

A backtest replays a strategy over past dates. On each **scan date** the engine sees only bars up to that date, runs the same pipeline as a full run (prefilter → shortlist → score → hard filters → plan), and every pick becomes a simulated trade that is then walked forward day by day with the same rules the Tracker uses. Nothing is predicted by the LLM; the backtest is pure engine code under `backend/app/engine/backtest/` (pure: no DB, no HTTP) driven by `services/backtest_service.py`.

`POST /backtests` body `BacktestBody` → 202 `Backtest` (status `queued`). Only one backtest runs at a time: 409 `{ "detail": "A backtest is already running", "backtest_id": n }` if another is queued or running.
`GET /backtests?profile_id=1&limit=20` → `Backtest[]` newest first (all profiles when `profile_id` omitted).
`GET /backtests/{id}` → `Backtest` (poll every 2 s while queued/running; `progress.phase` ∈ history | fundamentals | scanning | simulating | saving | done, `progress.done/total` = scan dates finished, `current_symbol` = scan date being processed).
`GET /backtests/{id}/results` → `BacktestResults`. 409 while not `done`.
`DELETE /backtests/{id}` → 204 (not while running → 409).

### Rules the simulation must follow
- **No look-ahead.** Histories passed to scoring and planning are cut to bars ≤ scan date; the plan is built with `trading_day = scan date`. A test must prove that adding or changing bars after the scan date never changes a scan's picks.
- **Scan dates.** `frequency: "weekly"` = the last trading day of each ISO week in [start_date, end_date]; `"daily"` = every trading day. Start is clamped so that at least 250 trading days of history exist before the first scan.
- **Entry.** `entry_rule: "next_close"` (default) fills at the close of the first trading day after the scan date, like pressing Track the next evening. `"optimal_limit"` fills at `entry_optimal` on the first of the next 5 sessions whose Low ≤ `entry_optimal`; if none, no trade is opened (counted in `summary.skipped_no_fill`). `qty = floor(capital_per_trade / fill price)`; qty 0 → skipped.
- **One open simulated trade per symbol.** A pick while the symbol's previous simulated trade is still open is skipped (counted in `summary.skipped_repeat`).
- **Exit**, checked on every session's close after entry, in this order: close ≤ stop → `stop_hit`; close ≥ target → `target_hit`; session date ≥ `planned_exit_date` → `horizon_closed`. Exit price is that session's close. Trades still open at `end_date` get `exit_reason: "open"`, are marked at the last close, and are excluded from win rate.
- **Costs.** `pnl = qty × (exit − entry) − invested × cost_pct / 100` (round trip, default 0.3 %). `r_multiple = (exit − entry) / (entry − stop)`.
- **Excursions.** `mfe_pct` / `mae_pct` = best / worst close vs entry, in %, while held. `nifty_pct` = Nifty 50 change from entry date to exit date (null if unavailable).
- **Fundamentals.** There is no free point-in-time fundamentals source, so the backtest is honest about it. `fundamentals_mode: "point_in_time"` (default): one bundle per symbol is fetched as of today and cached; quarterly and cash-flow rows whose period end is later than *scan date − 45 days* are dropped (results are published ~45 days after the quarter); `trailingPE` is recomputed as scan-date close ÷ sum of the last four surviving quarterly EPS (unavailable if fewer than four); `marketCap` is scaled by scan-date close ÷ today's close; 52-week high/low come from the truncated history. `returnOnEquity`, `debtToEquity`, `profitMargins`, `revenueGrowth` keep today's values, and `Backtest.caveats` says so. `"technical_only"`: weights of earnings_acceleration, fundamental_quality and valuation are set to 0 and the rest renormalised to 100; the P/E, ROE, debt, profit-growth and market-cap rules are skipped; caveats say so.
- **Loss patterns** are tagged deterministically on every losing trade with the Loss Analysis tag vocabulary, all that match: `stop_too_tight` (stopped out within 5 sessions and a later close before the planned exit date was above entry), `bought_extended` (fill more than 8 % above EMA20 on the fill day), `whole_market_fell` (nifty_pct ≤ −3), `held_too_long` (horizon_closed loss with mfe_pct ≥ half the target distance in %), `bad_entry_timing` (mae within the first 3 sessions ≥ half the risk), `low_liquidity` (avg 20-day turnover below ₹1 crore at scan date), else `other`.
- **Summary maths.** `win_rate_pct` = wins ÷ closed trades; `profit_factor` = gross wins ÷ gross losses (null if no losses); `expectancy_r` = mean r_multiple of closed trades; `total_pnl` in ₹ at `capital_per_trade`; `max_drawdown_pct` from the equity curve (cumulative closed P&L by exit date, as % of `capital_per_trade × 10`). `by_month` keys are `YYYY-MM` of the entry date.
- Price data: bhavcopy days needed for the range are downloaded and cached like a normal run; stocks whose history shows a possible corporate action are excluded by the existing rule.
- **Accepted backend decisions (2026-11-06).** Today's `earningsQuarterlyGrowth` is removed in point_in_time mode (it describes a quarter after the scan date). Operating margin keeps today's value and is named in the caveats. A trade with a one-day close move over 40 % while held is dropped and counted in the caveats. `skipped_no_fill` also counts picks the capital cannot afford one share of and picks on the last scan date. Open trades have null `exit_date` / `exit_price`; `total_pnl` includes them at the last close, the equity curve and drawdown use closed trades only. Loss patterns are tagged on closed losing trades only. A trade that exits on a scan date frees the symbol for a new pick that same date. Survivorship bias (stocks with no fundamentals today never appear) is always listed in the caveats.

```ts
export type ScanFrequency = 'weekly' | 'daily';
export type EntryRule = 'next_close' | 'optimal_limit';
export type FundamentalsMode = 'point_in_time' | 'technical_only';
export type BacktestExit = CloseReason | 'open';
export interface BacktestBody { profile_id: number; start_date: string; end_date: string; frequency?: ScanFrequency; entry_rule?: EntryRule; fundamentals_mode?: FundamentalsMode; cost_pct?: number; capital_per_trade?: number; }
export interface BacktestSummary { trades: number; closed: number; wins: number; losses: number; open_at_end: number; skipped_repeat: number; skipped_no_fill: number; win_rate_pct: number | null; avg_win_pct: number | null; avg_loss_pct: number | null; avg_pnl_pct: number | null; expectancy_r: number | null; profit_factor: number | null; total_pnl: number; max_drawdown_pct: number | null; avg_days_held: number | null; nifty_avg_pct: number | null; exits: { target_hit: number; stop_hit: number; horizon_closed: number; open: number }; }
export interface Backtest { id: number; profile_id: number; profile_name: string; status: RunStatus; start_date: string; end_date: string; frequency: ScanFrequency; entry_rule: EntryRule; fundamentals_mode: FundamentalsMode; cost_pct: number; capital_per_trade: number; params: Record<string, unknown>; progress: RunProgress; scan_count: number | null; summary: BacktestSummary | null; caveats: string[]; error: string | null; started_at: string | null; finished_at: string | null; created_at: string; }
export interface BacktestBreakdownRow { key: string; trades: number; win_rate_pct: number | null; avg_pnl_pct: number | null; total_pnl: number; }
export interface BacktestLossPattern { key: string; label: string; count: number; share_pct: number; }
export interface BacktestTrade { id: number; symbol: string; scan_date: string; entry_date: string; entry_price: number; qty: number; invested: number; stop_loss: number; target: number; planned_exit_date: string; signal: string; stage: string; score: number; market_cap_bucket: string; sector: string | null; exit_date: string | null; exit_price: number | null; exit_reason: BacktestExit; pnl: number; pnl_pct: number; r_multiple: number | null; days_held: number; mfe_pct: number | null; mae_pct: number | null; nifty_pct: number | null; tags: string[]; }
export interface EquityPoint { date: string; pnl: number; }
export interface BacktestResults { backtest: Backtest; by_signal: BacktestBreakdownRow[]; by_stage: BacktestBreakdownRow[]; by_market_cap: BacktestBreakdownRow[]; by_sector: BacktestBreakdownRow[]; by_month: BacktestBreakdownRow[]; loss_patterns: BacktestLossPattern[]; equity_curve: EquityPoint[]; trades: BacktestTrade[]; }
```
Defaults: `frequency` weekly, `entry_rule` next_close, `fundamentals_mode` point_in_time, `cost_pct` 0.3, `capital_per_trade` the profile's paper capital. Validation: `start_date < end_date`, `end_date` ≤ last trading day, `cost_pct` 0-5, range at most 3 years → 400.

Frontend (`/backtest`, sidebar item **Backtest** between Loss Analysis and Strategies): a **New backtest** form (strategy defaulting to the active one, date range defaulting to the last 12 months, frequency, entry rule, fundamentals mode with one-line help, cost %), a list of past backtests with status and progress, and a results page `/backtest/:id` with: stat tiles (trades, win rate, avg win / avg loss, expectancy R, profit factor, total P&L, max drawdown, vs Nifty), the caveats banner, the equity curve, breakdown tables (signal, stage, market cap, sector, month), the loss-pattern bar list using the Loss Analysis labels, and a sortable trades table (click a row → the symbol's row expands with plan numbers and tags; no dialog). **Compare**: choose two finished backtests and see their summaries side by side.

---

## Jobs (daily monitoring)

`POST /jobs/daily-update` → 202 `{ "started": true }` (runs in background; 200 `{ "started": false, "reason": "already running" }`).
`GET /jobs/status` → `{ "running": false, "last_daily_update": "2026-11-04T13:05:00Z", "last_trading_day": "2026-11-04", "next_scheduled": "2026-11-05T13:00:00Z", "last_summary": { "marked": 7, "closed_target": 1, "closed_stop": 0, "marked_due": 1 } }`

---

## Enumerations (exact strings)

`signal` (from `engine/scoring/signal.py`): `🟢 Early Setup`, `🟡 Developing`, `🔵 Breakout Confirmed`, `🟠 Extended`, `🔴 Weak / Invalidated`.
`stage` (from `engine/scoring/stage.py`): `Fundamental Change`, `Quiet Accumulation`, `Volume Expansion`, `Breakout`, `Momentum`, `Extended`.
`market_cap_bucket`: `Large Cap`, `Mid Cap`, `Small Cap`, `Unknown`.

## Ad-hoc analysis is persisted

`POST /stocks/{symbol}/analyze?profile_id=` saves its result as an ad-hoc suggestion (`source: "explore"`, no run) and returns it with a real `id`. Tracking from Explore therefore uses `POST /positions { profile_id, suggestion_id }` exactly like a run suggestion, so the position carries `stage`, `signal`, plan and reasons without re-analysing. Ad-hoc suggestions never appear in `GET /profiles/{id}/suggestions`. `SuggestionSummary.id` is therefore always a number; `source` is `"run"` or `"explore"`.

## TypeScript types (frontend copies verbatim)

```ts
export type RunStatus = 'queued' | 'running' | 'done' | 'failed';
export type RunKind = 'full' | 'watchlist';
export type Overall = 'buy' | 'watch' | 'avoid';
export type Trend = 'uptrend' | 'downtrend' | 'sideways';
export interface Verdict { overall: Overall; rules: { passed: number; total: number; failures: string[] }; chart: { trend: Trend; label: string; points: string[] }; reason: string; }
export type PositionStatus = 'open' | 'due' | 'closed';
export type CloseReason = 'target_hit' | 'stop_hit' | 'horizon_closed' | 'manual';
export type EventType = 'open' | 'extend' | 'shorten' | 'due' | 'close' | 'note';
export type FieldType = 'number' | 'int' | 'bool' | 'select' | 'multiselect';

export interface ParamField { key: string; label: string; type: FieldType; min?: number; max?: number; step?: number; options?: string[]; help?: string; }
export interface ParamSection { section: string; help?: string; fields: ParamField[]; }
export interface ParamSpec { defaults: Record<string, unknown>; horizons: string[]; cap_buckets: string[]; sections: ParamSection[]; }
export type Params = Record<string, number | boolean | string | string[]>;

export interface Profile { id: number; name: string; owner: string; is_active: boolean; params: Params; params_summary: string; created_at: string; updated_at: string; }

export interface PickList { id: number; name: string; symbols: string[]; created_at: string; updated_at: string; }
export interface CreatePickListBody { name: string; symbols: string[]; }
export interface UpdatePickListBody { name?: string; symbols?: string[]; }
export interface RunProgress { phase: string; done: number; total: number; current_symbol: string | null; }
export interface Run { id: number; profile_id: number; status: RunStatus; kind: RunKind; symbols: string[] | null; list_id: number | null; list_name: string | null; trading_day: string | null; progress: RunProgress; universe_size: number | null; scored_size: number | null; passed_size: number | null; error: string | null; started_at: string | null; finished_at: string | null; created_at: string; }

export type SuggestionSource = 'run' | 'explore' | 'watchlist';
export interface SuggestionSummary { id: number; source: SuggestionSource; verdict: Verdict; symbol: string; rank: number | null; score: number; stage: string; signal: string; price: number; entry_optimal: number; stop_loss: number; target: number; risk_reward: number; horizon_days: number; planned_exit_date: string; market_cap_bucket: string; sector: string | null; profit_yoy_pct: number | null; change_1m_pct: number | null; change_3m_pct: number | null; volume_ratio_20d: number | null; is_tracked: boolean; position_id: number | null; }
export interface Reasons { why_flagged: string; what_changed: string; positives: string[]; risks: string[]; }
export interface Plan { entry_aggressive: number; entry_optimal: number; entry_conservative: number; stop_loss: number; target: number; risk_reward: number; horizon_days: number; planned_exit_date: string; timing_note: string; exit_note: string; disclaimer: string; }
export interface PillarScore { key: string; label: string; score: number | null; max: number; weight: number; available: boolean; details: Record<string, number | string | null>; }
export interface Indicators { rsi: number | null; macd_signal: string | null; ema_trend: string | null; ema20: number | null; ema50: number | null; ema200: number | null; atr: number | null; bb_position: string | null; volume_ratio: number | null; }
export interface Fundamentals { pe: number | null; pb: number | null; roe_pct: number | null; debt_to_equity: number | null; market_cap: number | null; sector: string | null; industry: string | null; revenue_yoy_pct: number | null; profit_yoy_pct: number | null; eps_yoy_pct: number | null; operating_margin_pct: number | null; latest_ocf: number | null; }
export interface ChartData { dates: string[]; close: number[]; ema20: (number | null)[]; ema50: (number | null)[]; volume: number[]; }
export interface FilterResult { passed: boolean; failures: string[]; }
export interface SuggestionDetail extends SuggestionSummary { trading_day: string; reasons: Reasons; plan: Plan; score_breakdown: PillarScore[]; indicators: Indicators; fundamentals: Fundamentals; chart: ChartData; filters: FilterResult; }
export interface SuggestionsResponse { run: Run | null; items: SuggestionSummary[]; }

export interface StockRow { symbol: string; close: number; change_1d_pct: number | null; change_1w_pct: number | null; change_1m_pct: number | null; change_3m_pct: number | null; dist_from_52w_high_pct: number | null; volume_ratio_20d: number | null; avg_turnover_lacs: number | null; }
export interface StocksResponse { trading_day: string; total: number; items: StockRow[]; }
export interface StockDetail { symbol: string; trading_day: string; close: number; metrics: StockRow; indicators: Indicators; chart: ChartData; }

export interface Position { id: number; profile_id: number; suggestion_id: number | null; symbol: string; opened_on: string; entry_price: number; qty: number; invested: number; capital: number; cash_left: number; target: number | null; stop_loss: number | null; original_exit_date: string; planned_exit_date: string; status: PositionStatus; last_mark_date: string | null; last_close: number | null; current_value: number | null; pnl: number | null; pnl_pct: number | null; days_held: number; days_to_exit: number | null; closed_on: string | null; exit_price: number | null; close_reason: CloseReason | null; needs_review: boolean; stage: string | null; signal: string | null; }
export interface Mark { mark_date: string; close: number; value: number; pnl: number; pnl_pct: number; }
export interface PositionEvent { id: number; event_date: string; event_type: EventType; old_exit_date: string | null; new_exit_date: string | null; reason: string | null; price: number | null; created_at: string; }
export interface Benchmark { symbol: string; change_pct_since_open: number; }
export interface PositionDetail extends Position { marks: Mark[]; events: PositionEvent[]; suggestion: SuggestionSummary | null; benchmark: Benchmark | null; }
export interface ProfileStats { open: number; due: number; closed: number; wins: number; losses: number; win_rate_pct: number | null; avg_pnl_pct: number | null; avg_win_pct: number | null; avg_loss_pct: number | null; total_pnl: number; realised_pnl: number; unrealised_pnl: number; total_invested: number; best: { symbol: string; pnl_pct: number } | null; worst: { symbol: string; pnl_pct: number } | null; closed_by: Record<CloseReason, number>; extensions: { count: number; helped: number; hurt: number }; pending_reviews: number; }

export interface ReviewTag { key: string; label: string; }
export interface Review { id: number; position_id: number; symbol: string; pnl: number; pnl_pct: number; closed_on: string; close_reason: CloseReason; reasons: string[]; mistakes: string; lesson: string; algo_change: string; reviewed_on: string; created_at: string; }
export interface LossesResponse { pending: Position[]; reviewed: Review[]; }
export interface LossSummary { total_losses: number; reviewed: number; by_tag: { key: string; label: string; count: number }[]; avg_loss_pct: number | null; }

export interface Health { status: string; trading_day: string | null; db: string; }

// Request bodies
export interface CreateProfileBody { name: string; owner?: string; params?: Partial<Params>; }
export interface UpdateProfileBody { name?: string; owner?: string; params?: Partial<Params>; }
export interface StartRunBody { force_refetch?: boolean; }
export interface CreatePositionBody { profile_id: number; suggestion_id?: number; symbol?: string; capital?: number; }
export interface ChangeExitBody { new_exit_date: string; reason: string; }
export interface ClosePositionBody { reason: string; }
export interface NoteBody { note: string; }
export interface ReviewBody { reasons: string[]; mistakes: string; lesson: string; algo_change: string; }

export interface JobStatus { running: boolean; last_daily_update: string | null; last_trading_day: string | null; next_scheduled: string | null; last_summary: { marked: number; closed_target: number; closed_stop: number; marked_due: number } | null; }
```

---

## Proposed changes
(Coding agents append here; the guide accepts or rejects and updates the contract above.)

### Resolved 2026-11-05 (guide)
- total_pnl: **accepted, extended.** `total_pnl` covers all positions; added `realised_pnl` (closed) and `unrealised_pnl` (open + due).
- Weight fields: **accepted** via the section name rule; see "Scoring weights rule" under Profiles.
- Signal/stage strings: **corrected.** Weak is `🔴 Weak / Invalidated`, not `⚪ Weak`. Full list under "Enumerations".
- Health + request-body types: **accepted**, added to the TS block. Frontend moves them from `requests.ts` into `types/api.ts`.
- New (guide): ad-hoc analysis from Explore is persisted as a suggestion with `source: "explore"`; `SuggestionSummary.id` is never null and gains `source`. Backend: `suggestions.run_id` becomes nullable, add `source` column.

- 2026-11-05 (guide): single-user login added (see "Auth"); profiles reframed as strategies in the UI; `owner` hidden.

- 2026-11-05 (backend → accepted): `CreateProfileBody.owner` optional; TS updated, backend test exception removed.

- 2026-11-06 (guide): **Pick lists** added (named, saved My Picks lists; `Run.list_id`/`list_name`; `WatchlistRunBody` takes `list_id` or `symbols`). See the "Pick lists" section.

- 2026-11-06 (guide): **Backtests** added (see the "Backtests" section; types in the section's snippet, not duplicated in the main block).

### Open
- 2026-11-05 (frontend): **`WatchlistItem` error rows contradict their type.** The prose says an unknown or unscorable symbol comes back with `error` set "and score fields null", but `WatchlistItem extends SuggestionSummary`, where `id`, `score`, `price`, `entry_optimal`, `stop_loss`, `target`, `risk_reward`, `horizon_days`, `stage`, `signal`, `planned_exit_date` are all non-null, and `filters: FilterResult` is required. An unknown symbol also has no persisted suggestion, so there is no real `id`. Proposal: a discriminated union, so neither side has to guess:
  `export interface WatchlistHit extends SuggestionSummary { filters: FilterResult; error: null; }`
  `export interface WatchlistMiss { symbol: string; error: string; }`
  `export type WatchlistItem = WatchlistHit | WatchlistMiss;`
  Until this is decided, the UI renders an error row from `symbol` and `error` only and never reads the other fields, so it works with either shape.
- 2026-11-05 (frontend): **Duplicate `RunKind`.** The Watchlist snippet declares `export type RunKind`, and so does the main TS block, so copying both verbatim does not compile. Proposal: move `WatchlistRunBody`, `WatchlistItem` and `WatchlistResults` into the main TS block and drop the snippet's `RunKind` line. Frontend currently copies the snippet minus that one line.
- 2026-11-05 (frontend): **Which runs do the existing run endpoints return?** Please state whether `GET /profiles/{id}/runs` includes `kind: "watchlist"` runs, and confirm that `GET /profiles/{id}/suggestions?run_id=latest` means the latest finished **full** run (a watchlist run finishing later must not replace the Algo Suggested list). The UI's Algo Suggested progress bar only follows `kind: "full"` runs either way.
- 2026-11-05 (backend), on the three frontend items above:
  - **WatchlistItem shape, as implemented:** an analysed symbol is a full `SuggestionSummary` + `filters` + `error: null` (including ones that fail the filters). An unknown or unscorable symbol has `symbol`, `error`, `source: "watchlist"`, `filters: {passed: false, failures: []}`, `market_cap_bucket: "Unknown"`, `is_tracked`/`position_id` (by symbol), and `null` for `id` and every score/plan field (never 0). That satisfies both the current prose and the frontend's `WatchlistHit | WatchlistMiss` union, so backend needs no change whichever TS the guide picks. `tests/test_contract_schemas.py` carries a `PENDING_NULLABLE` exception for those `WatchlistItem` fields until the TS is updated.
  - **Run endpoints, as implemented:** `GET /profiles/{id}/runs` returns **full runs only** (watchlist runs are at `GET /profiles/{id}/watchlist-runs`), and `?run_id=latest` is the latest finished **full** run, so a later watchlist run never replaces the Algo Suggested list. Please write both into the contract.
  - **Other behaviour to confirm:** watchlist runs do not take the one-active-run-per-profile slot (a watchlist run starts even while a full run is going; two watchlist runs can run together). `GET /runs/{id}/results` on a full run → 400. While a watchlist run is in progress, `results` lists only symbols already analysed, still in requested order. Run counts for a watchlist run: `universe_size` = distinct symbols requested, `scored_size` = analysed, `passed_size` = passed the filters. `rank` is null for watchlist items.
  - ~~(frontend, live check 2026-11-05) unknown-symbol row mismatch~~ **Withdrawn by frontend 2026-11-05:** the accepted `WatchlistMiss` (ten fields, `filters: null`) matches what the backend returns; the frontend now types results as `WatchlistHit | WatchlistMiss` and its mocks follow it.
  - **DATA_MODEL.md:** `suggestion_runs` gained `kind` (default `full`), `symbols_json`, and `item_errors_json` (`{symbol: error}`; an unknown symbol has no suggestion row to hold its error). Added in place to the live DB; existing runs kept as `full`.
