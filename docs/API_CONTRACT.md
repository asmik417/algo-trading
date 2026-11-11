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
export interface WatchlistHit extends SuggestionSummary { decision: Decision; analyst: AnalystView | null; filters: FilterResult; error: null; }
export interface WatchlistMiss { id: null; symbol: string; error: string; filters: null; score: null; signal: null; stage: null; price: null; is_tracked: false; position_id: null; }
export type WatchlistItem = WatchlistHit | WatchlistMiss;
export interface WatchlistResults { run: Run; items: WatchlistItem[]; }
```

---

## Pick lists (named, saved lists for My Picks)

A pick list is a named set of symbols the user keeps and re-analyses, e.g. "Manager holdings". Lists are **independent of strategies**: the same list can be analysed under any strategy. Names are unique (case-insensitive, trimmed), 1-60 chars. The name "New list…" (any case, with `...` or `…`) is reserved for the UI's menu entry → 400. Symbols: 1-50, upper-cased, de-duplicated, order preserved.

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

## Decision (what the stock dialog leads with)

The dialog is a decision tool, not an information tool. Every `SuggestionDetail` and every `WatchlistHit` carries a `decision` built by deterministic code (`services/decision_service.py`) from the verdict, the plan, the indicators and the fundamentals. The LLM writes only `decision.narrative`, from the findings it is given, and may not introduce a number that is not in them.

```ts
export type Direction = 'up' | 'down' | 'sideways';
export interface Finding { side: 'for' | 'against'; text: string; }           // text always carries its number, e.g. "Delivery % fell from 51% to 39% during the surge"
export interface Expectation { direction: Direction; level: number | null; by_date: string; text: string; }
export interface ReviewRule { until: string; trigger: string; }               // "do not revisit before <until> unless <trigger>"
export interface Confidence { signal_win_rate_pct: number | null; trades: number | null; backtest_id: number | null; }
export interface Decision { overall: Overall; headline: string; findings: Finding[]; expectation: Expectation; review: ReviewRule; confidence: Confidence; narrative: string; }
```
`SuggestionDetail` and `WatchlistHit` gain `decision: Decision`. `Reasons` (why_flagged, what_changed, positives, risks) stays for compatibility but the UI no longer shows `why_flagged` / `what_changed`.

### How each field is computed (deterministic)
- `headline`: one sentence, template per overall. buy: "Buy <sym> near ₹<entry_optimal>: <chart label>, <strongest for-finding, short>." watch: "Wait on <sym>: <first failure or chart reason>." avoid: "Avoid <sym> for now: <first failure>; <chart label>." Holdings verbs (add / hold / trim / exit) come later and reuse this shape.
- `findings`: 3 to 6 items, most decisive first. Against: every failed rule that drove the verdict (max 3, in the verdict's order), then the chart points that are negative (below EMA, RSI over 70, falling delivery, MACD bearish, volume drying). For: positives from the engine that carry a number (profit growth, margin, PEG, delivery rising, volume, trend). Never a bare adjective; each item must carry a figure. Rules that were skipped for lack of data are not findings.
- `expectation`:
  - buy: `up`, `level = target`, `by_date = planned_exit_date`, text "Expect ₹<target> by <date> while it holds above ₹<stop>."
  - watch: `sideways`, `level = entry_optimal`, `by_date` = 20 trading days out, text "Expect a pullback toward ₹<entry_optimal>; becomes a Buy if it holds there and <first failure's fix>."
  - avoid with downtrend: `down`, `level = max(stop, 20-day low)`, `by_date` = 20 trading days out, text "Expect further weakness toward ₹<level> over the next 4 weeks."
  - avoid with uptrend or sideways: `sideways`, `level = null`, `by_date` = 20 trading days out, text "The price may hold up, but the numbers do not support buying: <first failure>."
- `review`: `until = by_date`; `trigger` = the fix for the first failure, phrased as a condition: "it closes above the 200-day EMA (₹<ema200>)", "RSI drops back under 70", "the next quarterly results show profit growth of 20% or more", "volume runs above 1.2× its average for 3 sessions", "P/E falls under 50 (price below ₹<price × 50/pe>)". For a Weak signal with no fix: "the signal turns to Early Setup or Breakout".
- `confidence`: from the latest finished backtest of the same profile, the `by_signal` row for this signal: `signal_win_rate_pct`, `trades`, `backtest_id`; all null if no backtest. UI text: "In our 12-month backtest this signal won <x>% of <n> trades."
- `narrative`: LLM, 2 to 4 sentences for a non-trader, written **only** from headline + findings + expectation + review. Deterministic fallback = headline + first two findings. Cached like `why_flagged` today.
- Existing rows: `decision` is rebuilt on read from stored data (like the verdict), so nothing needs re-scoring.

### Dialog layout (frontend)
1. **Header**: symbol, name/sector line, latest close, Track button. Big verdict badge and the `headline` beside it.
2. **Our call** card, two columns: *Expectation* (direction arrow, level, by date, text) and *Review* ("Do not revisit before <until> unless <trigger>"), with the confidence line underneath.
3. **Why** list: findings as a two-column list (for / against), then the `narrative` paragraph.
4. **Plan**: for buy, the three entry cards plus target/stop/exit as today. For watch, one line: "Buy zone ₹<entry_optimal>, stop ₹<stop>, target ₹<target>" and the entry cards collapsed. For avoid, collapsed under "Plan if the verdict changes".
5. **Details**, collapsed by default, one accordion with three rows: "Rules <passed>/<total>" (the failure list and the skipped list), "Chart & score" (price chart, score breakdown, indicator strip), "Fundamentals" (the grid). Nothing from Details appears above the fold.
6. Disclaimer line.
The table rows in Algo Suggested, Explore and My Picks keep their columns; the `headline` becomes the row tooltip.

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

## The brain (evidence packs, analyst view, market brief, scorecard)

Plan and method: `docs/BRAIN_PLAN.md`. All numbers come from code; the model reasons over an evidence pack and gives an opinion that is shown separately from the rules verdict and scored later.

### Sources and the nightly job
`POST /jobs/nightly-brain` body `{ "day"?: "YYYY-MM-DD" }` → 202 `{ "job_id": n }`; runs pull sources → point-in-time results → market brief → evidence packs → analyst views → verdict log → scorecard marks, for the latest trading day unless `day` given. Idempotent per day. 409 if already running.
`GET /jobs/status` gains `brain: { running: boolean; last_day: string | null; sources: SourceStatus[]; packs_built: number; views_built: number; views_failed: number } | null`.
The scheduler runs it right after the daily update on weekdays.

```ts
export interface SourceStatus { source: string; day: string; status: 'ok' | 'empty' | 'failed'; records: number; error: string | null; }
```

### Evidence pack
`GET /stocks/{symbol}/evidence?day=` → `EvidencePack` for that day (latest if omitted); 404 if none built. Built only for pick-list stocks, the day's algo suggestions and open positions; `POST /stocks/{symbol}/evidence` builds one on demand (synchronous, under 10 s) → 201.

```ts
// money in ₹ crore, eps in ₹, period = quarter-end date
export interface QuarterRow { period: string; filed_on: string | null; revenue: number | null; ebitda: number | null; net_profit: number | null; eps: number | null; margin_pct: number | null; }
export interface Ownership { as_of: string | null; promoter_pct: number | null; promoter_change_pct: number | null; fii_pct: number | null; dii_pct: number | null; public_pct: number | null; pledge_pct: number | null; }
export interface DealRow { date: string; kind: 'bulk' | 'block' | 'insider_buy' | 'insider_sell'; party: string; qty: number; price: number | null; }
export interface EventRow { date: string; kind: string; title: string; }
export interface Headline { date: string; title: string; source: string; url: string; }
export interface MarketContext { day: string; nifty_close: number | null; nifty_vs_ema50_pct: number | null; nifty_1w_pct: number | null; vix: number | null; advance_decline: number | null; fii_net_cr: number | null; dii_net_cr: number | null; sector_index: string | null; sector_1w_pct: number | null; sp500_1d_pct: number | null; crude_1w_pct: number | null; usdinr_1w_pct: number | null; }
export interface EvidencePack { symbol: string; day: string; price: { close: number; change_1w_pct: number | null; change_1m_pct: number | null; change_3m_pct: number | null; vs_nifty_1m_pct: number | null; vs_sector_1m_pct: number | null; dist_52w_high_pct: number | null; volume_ratio: number | null; delivery_pct_now: number | null; delivery_pct_prev: number | null; ema_trend: string | null; rsi: number | null; }; quarters: QuarterRow[]; ownership: Ownership | null; deals: DealRow[]; events: EventRow[]; headlines: Headline[]; market: MarketContext; rules_verdict: Verdict | null; plan: Plan | null; unavailable: string[]; }
```
`unavailable` names every section that could not be filled (`quarters`, `ownership`, `deals`, `events`, `headlines`, `rules_verdict`, `plan`) and single missing fields in dotted form (`price.vs_sector_1m_pct`, `ownership.fii_pct`, `market.vix`, `deals.insider`); sections are never fabricated. Windows: `price.change_*` = 5 / 21 / 63 sessions, deals 30 days, headlines 7 days, events = last 30 days plus known calendar events in the next 30. `dist_52w_high_pct` is against the highest close of 252 sessions; `delivery_pct_prev` is the 20-session average before today. Followed set for nightly packs: pick-list stocks, the latest finished full run of each profile, open and due positions.

### Analyst view
`POST /stocks/{symbol}/analyst-view?profile_id=` → 202 `{ "status": "queued" }` or 200 `AnalystView` if one exists for the day. `GET /stocks/{symbol}/analyst-view?day=&profile_id=` → `AnalystView` (profile defaults to the active one), 404 if none. `SuggestionDetail` and `WatchlistHit` gain `analyst: AnalystView | null` (the view for the row's trading day).

```ts
export type AnalystConfidence = 'low' | 'medium' | 'high';
export type AnalystAction = 'buy' | 'watch' | 'avoid' | 'add' | 'hold' | 'trim' | 'exit';
export type AnalystRunResult = { status: 'queued' } | AnalystView;
export interface AnalystView { id: number; symbol: string; day: string; profile_id: number; observations: string[]; anomalies: string[]; bull_case: string; bear_case: string; tests: { claim: string; evidence: 'present' | 'absent' | 'unknown'; note: string }[]; action: AnalystAction; direction: Direction; horizon_sessions: 20; confidence: AnalystConfidence; trigger: string; want_to_know: string; agrees_with_rules: boolean | null; audited: boolean; audit_notes: string[]; model: string; cost_usd: number | null; stale_days: number; created_at: string; }
```
Nightly policy (decided 2026-11-06): views are built only for pick-list stocks and open or due positions, and only when the stock's evidence changed since its last view: close moved 3 % or more, a new quarter was filed, a new deal, event or headline appeared, the rules verdict changed, or the market regime changed. Unchanged stocks keep yesterday's view (`AnalystView.stale_days` tells the UI how old it is). Cap `ANALYST_MAX_VIEWS_PER_NIGHT` 30. Model stays Opus 5.5; `ANALYST_EFFORT` defaults to `medium`.

Rules: the model is Claude Opus 5.5 with adaptive thinking; web search is allowed only to fetch news for the symbol and the result is appended to the pack's `headlines` before reasoning. Output is strict JSON. **Audit**: every number in the text fields must appear in the evidence pack (±1 % tolerance, percentages and rupees); on failure the model is re-asked once with the offending numbers listed; a second failure stores the view with `audited: false` and the UI shows it with a warning. `agrees_with_rules` compares `action` to the rules verdict's overall: agreeing pairs are buy↔buy/add, watch↔watch/hold, avoid↔avoid/exit/trim; else false; null when no rules verdict. The analyst is given the **profile's own** rules verdict for the day (the pack's `rules_verdict` is the active strategy's). Views are cached per (symbol, day, profile).

### Market brief
`GET /market/brief?day=` → `MarketBrief` (latest if omitted); `GET /market/briefs?limit=10` → `MarketBrief[]`.

```ts
export type Regime = 'risk_on' | 'neutral' | 'risk_off';
export interface MarketBrief { day: string; regime: Regime; audited: boolean; audit_notes: string[]; model: string; context: MarketContext; leaders: { index: string; change_1w_pct: number }[]; laggards: { index: string; change_1w_pct: number }[]; facts: string[]; paragraph: string; stance: string; created_at: string; }
```
`regime` is deterministic: risk_on if Nifty above EMA50, VIX under 15 and advance/decline over 1; risk_off if Nifty below EMA50 or VIX over 20 or FII net selling over ₹2,000 cr for 3 sessions; else neutral. `facts` are deterministic sentences with figures; `paragraph` and `stance` (one line, e.g. "Small caps weak; do not add, hold winners with stops") are written by the model from `facts` only and audited the same way.

### Verdict log and scorecard
Every rules verdict produced by a run, watchlist run or Explore analysis, and every analyst view, is logged once per (symbol, day, source, profile) with the close that day, the action, the direction and the level. The daily job marks each logged verdict at 20, 40 and 60 sessions after its day.

`GET /scorecard?profile_id=&source=rules|analyst|both&horizon=20|40|60` → `Scorecard`.
`GET /scorecard/verdicts?profile_id=&symbol=&limit=50` → `LoggedVerdict[]` newest first.

```ts
export type VerdictSource = 'rules' | 'analyst';
export interface LoggedVerdict { id: number; symbol: string; day: string; source: VerdictSource; profile_id: number; action: AnalystAction; direction: Direction; level: number | null; close: number; signal: string | null; marks: { sessions: 20 | 40 | 60; date: string; close: number; change_pct: number; right: boolean }[]; }
export interface ScorecardRow { key: string; verdicts: number; marked: number; right: number; hit_rate_pct: number | null; avg_change_pct: number | null; }
export interface Scorecard { profile_id: number; source: VerdictSource | 'both'; horizon: 20 | 40 | 60; total: ScorecardRow; by_source: ScorecardRow[]; by_action: ScorecardRow[]; by_signal: ScorecardRow[]; by_month: ScorecardRow[]; worst: LoggedVerdict[]; }
```
A mark is `right` when the change matches the direction: up → change > 0, down → change < 0, sideways → |change| ≤ 5.
`signal` on a logged verdict is the rules signal of the same symbol on the same day (from the suggestion row); an analyst verdict with no rules verdict that day has `null`, grouped as "No signal". `avg_change_pct` is the **change in the direction of the call**: up → change, down → −change; sideways verdicts are excluded from the average (null if none remain). The UI labels it "Avg edge".

### Frontend
- **Stocks page**: a market-brief banner at the top (regime badge, stance line, "Read brief" → `/market`).
- **`/market`**: the brief (facts, paragraph, leaders, laggards, context tiles) and a list of past briefs.
- **Stock dialog**: an **Analyst view** block under "Our call": action and confidence badges, "agrees with rules" chip, anomalies first, bull and bear case side by side, the tests table, trigger and want-to-know lines, the audit warning when `audited` is false, and a **Run analyst** button when `analyst` is null (polls until the view exists). The evidence pack is a fourth row in the Details accordion.
- **`/scorecard`**: controls for profile, source and horizon; stat tiles (verdicts, marked, hit rate, average change); tables by source, action, signal and month; the worst-misses list with a link to each symbol's dialog.
- Sidebar order: Stocks, Tracker, Holdings, Scorecard, Loss Analysis, Backtest, Strategies.

---

### Backtest, plain mode (story, money at work, winners vs losers, replay, experiments)

The results page must be readable by someone who has never traded. Numbers stay in the API; the frontend turns them into fixed plain sentences (no LLM).

`BacktestSummary` gains: `invested_total: number` (sum of `invested` over all trades), `peak_capital: number`, `peak_capital_date: string`, `peak_open_positions: number`, `return_on_peak_pct: number | null` (`total_pnl / peak_capital`), `nifty_period_pct: number | null` (Nifty from start to end date), `best_month: { key: string; pnl: number } | null`, `worst_month: { key: string; pnl: number } | null`, `quarters_from_filings: number`, `quarters_from_yfinance: number`.
`BacktestResults` gains `capital_curve: { date: string; at_work: number; open_positions: number }[]` (money invested in open trades per session) and `splits: SplitRow[]`.
`BacktestTrade` gains the entry snapshot: `rsi_at_entry: number | null`, `dist_ema20_pct: number | null`, `volume_ratio_at_entry: number | null`, `nifty_vs_ema50_pct_at_entry: number | null`, `regime_at_entry: Regime | null`, `pillars_at_entry: Record<string, number> | null`.

```ts
export interface SplitSide { trades: number; win_rate_pct: number | null; avg_pnl_pct: number | null; }
export interface SplitRow { feature: string; condition: string; when_true: SplitSide; when_false: SplitSide; gap_pct: number | null; }
```
`splits` is computed over closed trades for a fixed list of conditions, each side needing at least 10 trades (else `gap_pct` null, row still listed): RSI at entry > 65; RSI at entry < 50; price > 5 % above EMA20 at entry; volume ratio > 2 at entry; score ≥ 75; each signal; each stage; each market-cap bucket; Nifty below its 50-day EMA at entry; Nifty fell ≥ 3 % while held; sector fell ≥ 3 % while held; each sector with ≥ 10 trades; entry in a `risk_off` regime; held past 30 sessions. Sorted by |gap_pct| desc. `gap_pct = when_true.win_rate_pct − when_false.win_rate_pct`.

**Trade replay.** `GET /backtests/{id}/trades/{trade_id}` → `{ trade: BacktestTrade; chart: ChartData; nifty: { date: string; close: number }[]; markers: { date: string; kind: 'scan' | 'entry' | 'exit' | 'stop' | 'target'; price: number | null }[]; events: EventRow[] }` where `chart` covers 60 sessions before entry to 10 after exit, with EMA20/EMA50 as in the stock dialog.

**Point-in-time fundamentals.** In `fundamentals_mode: "point_in_time"`, when `quarterly_results` holds at least four quarters filed before the scan date for a symbol, those filed numbers are used for the earnings and valuation pillars and the profit-growth and P/E rules; otherwise the existing yfinance truncation applies. `summary.quarters_from_filings` / `quarters_from_yfinance` count symbol-scans by source, and the caveats name both counts.

**Experiments.** An experiment is one change tested against a baseline.
`GET /experiments?limit=50` → `Experiment[]`; `POST /experiments` body `{ name, hypothesis, baseline_backtest_id, changes: Record<string, unknown> }` → 201 `Experiment`: the server clones the baseline's strategy as "<name> · exp <id>" with `changes` applied to its params (same validation as PUT /profiles), starts a candidate backtest with the baseline's settings and dates, and links it. `PUT /experiments/{id}` body `{ verdict?: 'kept' | 'discarded', notes?: string }`. `DELETE /experiments/{id}` → 204 (deletes the cloned strategy too if it has no positions).

```ts
export type ExperimentVerdict = 'pending' | 'kept' | 'discarded';
export interface Experiment { id: number; name: string; hypothesis: string; baseline_backtest_id: number; candidate_backtest_id: number; candidate_profile_id: number; changes: Record<string, unknown>; verdict: ExperimentVerdict; notes: string; delta: { trades: number; win_rate_pct: number | null; expectancy_r: number | null; total_pnl: number; max_drawdown_pct: number | null } | null; created_at: string; }
```
`delta` = candidate minus baseline summary, null until the candidate is done.

**Frontend.**
- Results page top = the **story**, five sentences from the summary: trades and period; invested_total, peak_capital on peak_capital_date in peak_open_positions stocks; total_pnl and return_on_peak_pct versus nifty_period_pct; win rate with average winner and loser in ₹ (avg_win_pct × capital_per_trade); best and worst month. Below it the existing tiles, each with a hover glossary in plain words (fixed dictionary in `lib/glossary.ts`).
- Money chart shows two lines: cumulative P&L ("your profit so far") and `at_work` ("money invested at the time").
- A **Winners vs losers** table from `splits` (feature, condition, win rate when true / false, gap, trades), rows with |gap| ≥ 10 points highlighted, each with a "Test this" button that opens the New experiment form with the matching parameter prefilled where one exists.
- Trades table reads like a passbook: bought on, price, qty, invested, sold on, why, result ₹ and %. Row click opens the **replay** (chart with markers, Nifty line, events, the entry snapshot).
- `/backtest/experiments`: the log (name, hypothesis, change, baseline vs candidate deltas, verdict, notes) and the New experiment form (baseline backtest, name, hypothesis, parameter changes from the strategy form).
- Loss-pattern bars stay but move below the splits table.

---

## Intraday (DRAFT: UI on mocks only, backend not started)

Mock at https://claude.ai/artifact/5dY5GzavTSMAivhC6VLkpn (five screens). The app gains a top-level mode switch **Positional | Intraday** above the sidebar; the sidebar under Intraday is Today, Paper trades, Playbook, Backtest, Scorecard. Routes `/intraday`, `/intraday/trades`, `/intraday/playbook`, `/intraday/backtest`, `/intraday/scorecard`. The chosen mode is kept in `localStorage` (`mode`). Endpoints below are the shape the backend will implement; until then the frontend serves them from mocks regardless of `VITE_USE_MOCKS` (an `intradayMocks` flag, default on).

`GET /intraday/today` → `IntradayToday` (poll every 5 s during market hours). `GET /intraday/signals/{id}` → `IntradaySignal`. `POST /intraday/trades` body `{ signal_id }` → 201 `IntradayTrade`. `POST /intraday/trades/{id}/exit` body `{ reason?: string; fraction?: 1 | 0.5 }` → `IntradayTrade`. `GET /intraday/trades?day=` → `{ open: IntradayTrade[]; signals: IntradaySignal[]; days: IntradayDay[] }`. `GET /intraday/playbook` → `Playbook`; `PUT /intraday/playbook` → `Playbook`. `GET /intraday/scorecard?days=20` → `IntradayScorecard`.

```ts
export type SetupState = 'waiting' | 'armed' | 'triggered' | 'in_trade' | 'exited' | 'failed' | 'skip';
export type SignalKind = 'range_breakout' | 'vwap_pullback';
export interface MarketPulse { time: string; nifty: number; nifty_change_pct: number; nifty_above_opening_range: boolean | null; vix: number | null; advances: number | null; declines: number | null; regime: Regime; }
export interface SureDayCheck { label: string; points: number; earned: number; }
export interface SureDay { score: number; threshold: number; trade_day: boolean; checks: SureDayCheck[]; }
export interface StockInPlay { symbol: string; price: number; gap_pct: number; rel_volume: number; score: number; why: string; state: SetupState; state_note: string; range_high: number | null; range_low: number | null; }
export interface IntradaySignal { id: number; time: string; symbol: string; kind: SignalKind; score: number; buy: number; buy_limit: number; qty: number; invested: number; stop: number; target: number; risk_rs: number; reward_rs: number; r_multiple: number; valid_until: string; square_off_at: string; why: string; checks: { label: string; passed: boolean; half?: boolean }[]; cancel_if: string; plain_words: string; confidence: { label: 'low' | 'medium' | 'high'; score: number; backtest_win_rate_pct: number | null; backtest_trades: number | null; backtest_avg_r: number | null }; chart: { time: string; open: number; high: number; low: number; close: number; volume: number; vwap: number | null }[]; taken: boolean; outcome_note: string | null; }
export interface RiskToday { capital: number; leverage: number; buying_power: number; max_trades: number; trades_used: number; stop_after_losses: number; max_risk_rs: number; entry_windows: string[]; square_off_at: string; day_pnl: number; day_target_rs: number; }
export interface TimelineEvent { time: string; text: string; done: boolean; }
export interface IntradayToday { day: string; market_open: boolean; pulse: MarketPulse; sure_day: SureDay; stocks: StockInPlay[]; hidden_below_line: number; signals: IntradaySignal[]; risk: RiskToday; timeline: TimelineEvent[]; feed: { source: string; lag_seconds: number | null } | null; }
export interface IntradayTrade { id: number; signal_id: number; symbol: string; entered_at: string; qty: number; entry: number; stop: number; stop_moved_to_breakeven_at: string | null; target: number; last: number; pnl: number; pnl_pct_of_capital: number; progress_pct: number; engine_says: string; next_check: string; exited_at: string | null; exit_price: number | null; exit_reason: 'target' | 'stop' | 'time' | 'manual' | 'rule' | null; }
export interface IntradayDay { day: string; sure_day_score: number; traded: boolean; trades: { symbol: string; pnl: number }[]; pnl: number; capital_after: number; hit_target: boolean | null; note: string; }
export interface Playbook { id: number; name: string; in_play: { min_gap_pct: number; min_rel_volume: number; needs_catalyst: boolean; min_turnover_cr: number; price_min: number; price_max: number; min_atr_pct: number; score_line: number }; entry: { range_minutes: number; confirm: string; min_breakout_volume: number; gap_direction_only: boolean; nifty_must_agree: boolean; max_chase_pct: number; windows: string[] }; risk: { stop_rule: string; target_r: number; breakeven_after_r: number; max_risk_pct: number; max_trades: number; stop_after_losses: number; square_off_at: string; leverage: number }; sure_day: { checks: { label: string; points: number }[]; threshold: number }; last_backtest: { days: number; traded_days: number; win_rate_pct: number; avg_win_rs: number; avg_loss_rs: number; net_rs: number; worst_run_rs: number; target_days: number; biggest_lever: string } | null; }
export interface IntradayScorecard { days: number; started_rs: number; started_on: string; now_rs: number; days_traded: number; trades: number; wins: number; avg_win_rs: number; avg_loss_rs: number; target_days: number; worst_day: { day: string; pnl: number } | null; equity: { day: string; capital: number; traded: boolean }[]; live_vs_backtest: { metric: string; live: string; backtest: string }[]; drift_note: string | null; cuts: { label: string; signals: number; taken: number; win_rate_pct: number; avg_rs: number; suggests: string }[]; }
```

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
export interface SuggestionSummary { id: number; source: SuggestionSource; verdict: Verdict; headline: string; symbol: string; rank: number | null; score: number; stage: string; signal: string; price: number; entry_optimal: number; stop_loss: number; target: number; risk_reward: number; horizon_days: number; planned_exit_date: string; market_cap_bucket: string; sector: string | null; profit_yoy_pct: number | null; change_1m_pct: number | null; change_3m_pct: number | null; volume_ratio_20d: number | null; is_tracked: boolean; position_id: number | null; }
export interface Reasons { why_flagged: string; what_changed: string; positives: string[]; risks: string[]; }
export interface Plan { entry_aggressive: number; entry_optimal: number; entry_conservative: number; stop_loss: number; target: number; risk_reward: number; horizon_days: number; planned_exit_date: string; timing_note: string; exit_note: string; disclaimer: string; }
export interface PillarScore { key: string; label: string; score: number | null; max: number; weight: number; available: boolean; details: Record<string, number | string | null>; }
export interface Indicators { rsi: number | null; macd_signal: string | null; ema_trend: string | null; ema20: number | null; ema50: number | null; ema200: number | null; atr: number | null; bb_position: string | null; volume_ratio: number | null; }
export interface Fundamentals { pe: number | null; pb: number | null; roe_pct: number | null; debt_to_equity: number | null; market_cap: number | null; sector: string | null; industry: string | null; revenue_yoy_pct: number | null; profit_yoy_pct: number | null; eps_yoy_pct: number | null; operating_margin_pct: number | null; latest_ocf: number | null; }
export interface ChartData { dates: string[]; close: number[]; ema20: (number | null)[]; ema50: (number | null)[]; volume: number[]; }
export interface FilterResult { passed: boolean; failures: string[]; }
export interface SuggestionDetail extends SuggestionSummary { trading_day: string; decision: Decision; analyst: AnalystView | null; reasons: Reasons; plan: Plan; score_breakdown: PillarScore[]; indicators: Indicators; fundamentals: Fundamentals; chart: ChartData; filters: FilterResult; }
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

export interface BrainStatus { running: boolean; last_day: string | null; sources: SourceStatus[]; packs_built: number; views_built: number; views_failed: number; }
export interface NightlyBrainBody { day?: string; }
export interface NightlyBrainStarted { job_id: number; }
export interface JobStatus { brain: BrainStatus | null; running: boolean; last_daily_update: string | null; last_trading_day: string | null; next_scheduled: string | null; last_summary: { marked: number; closed_target: number; closed_stop: number; marked_due: number } | null; }
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

- 2026-11-06 (guide): **Decision** added (dialog leads with verdict, proof, expectation, review rule; details collapsed). `SuggestionDetail` and `WatchlistHit` gain `decision`. Types live in the Decision section's snippet.

- 2026-11-06 (guide): **The brain** added: sources, evidence packs, analyst view, market brief, verdict log and scorecard. See `docs/BRAIN_PLAN.md`; types in that section's snippet.

- 2026-11-06 (frontend → accepted): `LoggedVerdict.signal` added; `avg_change_pct` defined as change in the direction of the call, sideways excluded, labelled "Avg edge".

### Resolved 2026-11-06 (guide), the brain and Decision proposals
- Backend part 1: **all accepted.** `BrainStatus`, `NightlyBrainBody`, `NightlyBrainStarted` added to the TS block; `JobStatus.brain` added. DATA_MODEL updated (news_items, brain_jobs, long market_context, uid/pulled_day/data_json, source_pulls.inserted). Insider stays `failed` with reason until a browser-session fetch is approved; deals and FII/DII are latest-session only; intraday index pulls store nothing; `fii_pct`/`dii_pct` stay null; ET Markets + Google News for news; results method as described.
- Backend part 2: **all accepted.** `MarketBrief` gains `audited`, `audit_notes`, `model`. Units, windows, dotted `unavailable` names, sector mapping, regime reading, evidence POST behaviour and the followed set are now in the Evidence pack and Market brief prose. For the analyst view (part 3) the service passes the profile's own rules verdict.
- Frontend: **all accepted.** `SuggestionSummary.headline` (rebuilt on read); `AnalystConfidence` rename; `analyst` on `SuggestionDetail`/`WatchlistHit`; `AnalystRunResult`; `GET …/analyst-view` takes `profile_id` defaulting to active; agreeing pairs widened to buy↔buy/add, watch↔watch/hold, avoid↔avoid/exit/trim; QuarterRow units stated; scorecard `signal` and directional `avg_change_pct` ("Avg edge") were resolved in the previous commit.

### Resolved 2026-11-06 (guide), part 3 and nightly cost
- Part 3 proposals: **all accepted** (what the analyst is given, search behaviour and the basic search tool, audit allowances, failure handling, verdict-log mapping, worst ranking, DATA_MODEL additions). `AnalystView` gains `cost_usd` and `stale_days`.
- Nightly cost: **views only for pick lists and positions, and only when the evidence changed** (rules under "Nightly policy"); cap 30 a night; model unchanged; `ANALYST_EFFORT=medium`.
- Plan timing note: "Volume is picking up" may only be written when the volume ratio is ≥ 1.2; otherwise "Volume is quiet (0.3× average)". Fix in `plan_service`.
- Backtests #1 to #3 ran on poisoned fundamentals: **delete them.** Strategy id 8: delete it only if the backend agent created it for a test and nothing references it; otherwise leave it.
- New: "Backtest, plain mode" section above.

- 2026-11-11 (guide): **Intraday (DRAFT)** section added for the frontend to build on mocks; backend not started; types may change when the data feed is decided.

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
- 2026-11-06 (backend), **the brain, part 1 (sources)**:
  - **`JobStatus` TS lacks `brain`.** The prose under "Sources and the nightly job" adds it, but the main TS block's `JobStatus` (line ~526) does not. Proposal: add `brain: BrainStatus | null;` and `export interface BrainStatus { running: boolean; last_day: string | null; sources: SourceStatus[]; packs_built: number; views_built: number; views_failed: number; }`. `brain` is `null` until the first nightly-brain run. `tests/test_contract_schemas.py` carries a `PENDING_EXTRA` exception for it.
  - **Request/response types for `POST /jobs/nightly-brain`.** Proposal: `export interface NightlyBrainBody { day?: string }` and `export interface NightlyBrainStarted { job_id: number }`. A bad `day` gets 400, like other date bodies.
  - **DATA_MODEL additions, as implemented:**
    - `news_items` (symbol nullable for market-wide feeds, date, title, source, url).
    - `brain_jobs` (id, day, status queued/running/done/failed, summary_json, error, started/finished/created_at). This is what `job_id` refers to.
    - `market_context` is stored long, one row per `(day, metric)`, for example `vix`, `fii_net_cr`, `index:NIFTY 50:pct_1d` or `global:sp500:change_1w_pct`. `MarketContext` is assembled from it in part 2.
    - Every source row has `uid` (unique), `pulled_day` and `data_json`; inserts use `ON CONFLICT DO NOTHING`.
    - `source_pulls` also stores `inserted`.
  - **Source limits found while building (no contract change, but the guide should know):**
    - **Insider (PIT) is blocked.** NSE's `corporates-pit` returns 0 rows to any non-browser client. The source is recorded as `failed` every night, with that reason, and never `empty`. `DealRow` `insider_buy`/`insider_sell` will be absent until a browser-session fetch is approved.
    - **Deals and FII/DII are latest-session only.** NSE serves only today's snapshot, so a back-dated pull fails with a reason rather than storing the wrong day.
    - **Index levels are live.** A pull before 15:30 IST marks indices as intraday (status ok, with a warning in `error`) and stores no index rows.
    - **`Ownership.fii_pct`/`dii_pct` are not in NSE's shareholding master**, which gives only promoter and public. They stay `null` (unavailable) unless the guide wants the per-filing XBRL parsed.
    - **Moneycontrol RSS has been frozen since April 2024.** News uses the ET Markets feeds plus Google News per followed company.
    - **Quarterly results** come from NSE "Integrated Filing – Financials" XBRL, with `filed_on` taken from the broadcast date. EBITDA = PBT + finance costs + depreciation − other income. Banks report revenue as interest earned.
- 2026-11-06 (backend), **the brain, part 2 (evidence packs and market brief)**, as built:
  - **`MarketBrief` needs `audited: boolean`.** The paragraph and stance are audited like the analyst view: one re-ask listing the offending numbers. If the second answer also fails, or the model is unavailable, the brief falls back to deterministic text: the facts as the paragraph, plus a fixed stance per regime. The UI cannot tell this text from the model's without the flag. It is stored now (`market_briefs.audited`, `audit_notes_json`, `model`), but the response has no field for it yet.
  - **Units and definitions not stated in the contract:**
    - `QuarterRow.period` is the quarter-end date (`YYYY-MM-DD`).
    - `QuarterRow.revenue`, `ebitda` and `net_profit` are in ₹ crore; `eps` is in ₹.
    - `price.change_*` cover 5, 21 and 63 sessions.
    - `vs_nifty_1m_pct` and `vs_sector_1m_pct` are percentage points: the stock's 1-month change minus the index's.
    - `dist_52w_high_pct` is measured against the highest close of the last 252 sessions.
    - `delivery_pct_now` is the day's delivery %; `delivery_pct_prev` is the average of the 20 sessions before it.
    - Windows: deals cover 30 days and headlines 7 days. Events are the announcements of the last 30 days, plus calendar events in the next 30 days that were already known on the day.
  - **`unavailable`** holds section names (`quarters`, `ownership`, `deals`, `events`, `headlines`, `rules_verdict`, `plan`) plus dotted names for single missing fields (`price.vs_sector_1m_pct`, `ownership.fii_pct`, `market.vix`, `deals.insider`). Please confirm the dotted form.
  - **`market.sector_index`** maps Yahoo's sector and industry to an NSE sector index (table in `services/evidence_service.py`). For example, Ramkrishna Forgings, which Yahoo lists under Industrials, maps to NIFTY INFRASTRUCTURE.
  - **Market context sources:**
    - Index levels and their 1-week and 1-month changes come from NSE's end-of-day snapshot when it was pulled after 15:30.
    - Otherwise they come from Yahoo, which covers 18 indices. Nifty Smallcap and Midcap 150 are NSE-only.
    - `advance_decline` is computed from the whole NSE bhavcopy (every stock that traded on both sessions), so it is available for any past day. NSE's Nifty 500 count is kept in `market_context` but is not used.
  - **Regime reading:**
    - "FII net selling over ₹2,000 cr for 3 sessions" is read as each of the last 3 sessions below −₹2,000 cr.
    - That needs all 3 sessions pulled. NSE serves flows for the latest day only, so it takes 3 consecutive nightly runs.
    - An input that is unavailable never triggers a rule, and risk_on needs all three of its inputs.
    - Boundaries are strict: VIX at exactly 15 is not risk_on, and exactly 20 is not risk_off.
  - **`rules_verdict` / `plan` in a pack:**
    - The source is the stock's stored suggestion for that day, the active strategy's first.
    - With no stored suggestion, it is the active strategy run on the history up to that day, and that result is not saved.
    - Part 3's per-profile analyst view may want the profile's own verdict instead.
  - **`POST /stocks/{symbol}/evidence`:**
    - Rebuilds and replaces the pack for the latest day.
    - The first build for a stock with fewer than 4 stored quarters fetches its last 5 filings from NSE, about 6 s at NSE's pace, so a never-seen stock comes close to the 10 s budget. Afterwards a build takes 0–2 s.
    - On the latest day only, it fetches Google News for the stock when no headlines are stored.
  - **Followed set** for the nightly packs: pick lists, the latest finished full run of each profile (so "the day's suggestions" is the current Algo Suggested list), and open or due positions. Please confirm.
  - **DATA_MODEL:**
    - `evidence_packs`: `(symbol, day)` unique.
    - `market_briefs`: gains `audited`, `audit_notes_json` and `model`.
    - The nightly summary gains `brief` (`{regime, audited}`) and `packs_failed` (`{symbol: why}`).
- 2026-11-06 (frontend): **Row tooltips need the headline on the list rows.** The Dialog layout says the `headline` becomes the row tooltip in Algo Suggested, Explore and My Picks, but only `SuggestionDetail` and `WatchlistHit` carry `decision`. Algo Suggested rows are `SuggestionSummary` (no headline) and Explore rows are `StockRow` (not analysed yet, so no decision exists). Today the UI shows the headline on My Picks rows always, and on Algo Suggested / Explore rows only once that stock's detail or analysis has been loaded (read from cache, no extra requests; Explore rows otherwise say "Analyse <symbol> under <strategy>"). Proposal: add `headline: string` to `SuggestionSummary` (rebuilt on read like the verdict), so every Algo Suggested row gets its tooltip without fetching details. Explore stays as is (there is no decision before analysis).
- 2026-11-06 (frontend): **The brain's snippet clashes with Decision on `Confidence`.** Decision declares `interface Confidence { signal_win_rate_pct; trades; backtest_id }`; The brain declares `type Confidence = 'low' | 'medium' | 'high'`. Both copied verbatim into one module do not compile. Frontend keeps the brain's snippet in its own module (`types/brain.ts`) for now. Proposal: rename the brain's type to `AnalystConfidence` (used only by `AnalystView.confidence`).
- 2026-11-06 (frontend): **`analyst` and `JobStatus.brain` are in the prose but not in the TS.** The prose says `SuggestionDetail` and `WatchlistHit` gain `analyst: AnalystView | null` and `GET /jobs/status` gains `brain: {…} | null`, but neither TS block declares them. Proposal: add `analyst: AnalystView | null` to both interfaces and `brain: BrainStatus | null` to `JobStatus`, with `export interface BrainStatus { running: boolean; last_day: string | null; sources: SourceStatus[]; packs_built: number; views_built: number; views_failed: number; }`. Also name the POST result: `export type AnalystRunResult = { status: 'queued' } | AnalystView;`. Frontend declares these three under a marked block in `types/brain.ts` until then. When `analyst` is missing from a detail (older backend), the dialog asks `GET /stocks/{symbol}/analyst-view` instead.
- 2026-11-06 (frontend): **`GET /stocks/{symbol}/analyst-view` has no `profile_id`.** Views are cached per (symbol, day, profile) and the POST takes `profile_id`, but the GET takes only `day`, so with two strategies it is ambiguous which view comes back (the UI polls this GET after "Run analyst"). Proposal: `GET /stocks/{symbol}/analyst-view?day=&profile_id=` (profile defaults to the active one). Frontend sends only `day` today, as written.
- 2026-11-06 (frontend): **`agrees_with_rules` is false when both say Watch.** By the rule (buy↔buy, avoid↔avoid/exit, else false), an analyst Watch on a rules Watch counts as "does not agree", which reads wrong in the dialog. Proposal: add watch↔watch (and hold↔watch, if intended) to the agreeing pairs. The UI shows `false` as "Does not agree with rules" and `null` as "No rules verdict to compare".
- 2026-11-06 (frontend): **Units for `QuarterRow` money fields.** `revenue`, `ebitda` and `net_profit` have no stated unit (rupees or ₹ crore?), nor does `eps` (₹ per share, presumably). The evidence row shows them as plain numbers until the unit is written down. Proposal: state "₹ crore" (the unit results are filed in) for the three totals and "₹" for `eps`.
- 2026-11-06 (frontend): **Scorecard: what `avg_change_pct` and `by_signal` mean.** (1) Is `avg_change_pct` the plain average price change of the marked verdicts at the horizon (so Avoid calls that worked pull it down), or the change signed by direction (positive = moved the way the call said)? The UI labels it "price change after N sessions" and the mock uses the plain average. (2) `by_signal` groups by a signal that `LoggedVerdict` does not carry; please state that an analyst verdict takes the rules signal of the same (symbol, day), and consider adding `signal: string | null` to `LoggedVerdict` so the worst-misses list can show it.
- 2026-11-06 (backend), **the brain, part 3 (analyst view, verdict log, scorecard)**, as built:
  - **What the analyst is given:**
    - The pack, with `rules_verdict` and `plan` replaced by the profile's own.
    - `strategy` (the profile's name), `is_holding` and `market_regime` (from the day's brief).
    - A `derived` block computed by code, so the model never has to compute: latest-quarter YoY and QoQ for revenue, EBITDA and net profit; margin change in points; close vs the entry, upside to the target and downside to the stop in %; and, for a holding, entry price, return so far, target, stop and exit date.
    - URLs are stripped, because their digits would pollute the audit.
    - A stock with an open or due position under that profile gets `add / hold / trim / exit`; any other stock gets `buy / watch / avoid`. The JSON schema enforces this.
  - **Web search:**
    - It is a separate, low-effort call with at most 2 searches, made only on the latest day and only when the pack has fewer than 3 headlines. The analysis call has no tools.
    - Headlines are taken only from the search tool's own result blocks (title, URL, page age within 7 days), never from the model's text. They are stored in `news_items` and appended to the stored pack.
    - It uses the basic `web_search_20250305`, not `_20260209`, whose dynamic filtering routes results through code execution and would not give those raw result blocks.
  - **Audit:** the numbers written into the instructions are allowed (20 sessions, the ±5 band), as are numbers that are names: Nifty 50, S&P 500, the 50- and 200-day EMAs, and the 52-week high.
  - **Failures:** a view whose model call fails is not stored. `GET …/analyst-view` then returns 404 with the reason of the last attempt.
  - **`POST …/analyst-view`** always targets the latest trading day.
  - **Cost:** the Manager holdings run cost **$2.56 for 18 views, $0.14 average** (range $0.04 to $0.30): input $4 and output $20 per million tokens, plus $0.01 per search. Most of that run was re-asked once because "S&P 500" was not yet allowed; with that fixed, a view costs about $0.04 to $0.13 without a search and $0.15 to $0.25 with one.
  - **Nightly cost needs a decision.** The nightly job builds one view per followed stock (55 today) under the active strategy, capped by `ANALYST_MAX_VIEWS_PER_NIGHT` (default 60). That is about $5 to $8 a night (₹450 to ₹750), roughly ₹10,000 to ₹15,000 a month, not the few hundred rupees in BRAIN_PLAN. Options:
    - views only for pick lists and positions;
    - `ANALYST_EFFORT=low`;
    - a cheaper model through `ANALYST_MODEL`.
  - **Verdict log, as implemented:**
    - Rules overall maps to a direction: buy → up, watch → sideways, avoid → down.
    - `level` is the plan target for up, the stop for down, and null for sideways and for analyst views.
    - A rules verdict's `close` is the suggestion's price, which is the close of its trading day.
    - The first verdict per (symbol, day, source, profile) wins. A second Explore analysis the same day is not logged again.
    - Rules verdicts are logged by an incremental sweep of saved suggestions: in the daily job, the nightly job and before every scorecard read. Analyst views are logged when stored.
    - Marks are added in the daily job and the nightly job.
  - **`worst`:** the 10 wrong marks at the horizon with the biggest miss. For up or down calls, the miss is the move against the call. For sideways calls, it is how far the price ended outside the ±5 % band.
  - **DATA_MODEL:**
    - `analyst_views` gains `evidence_json` (exactly what the model saw), `usage_json` and `cost_usd`.
    - New tables: `verdict_log` and `verdict_marks`, as documented.
    - `app_meta.verdict_log_suggestion_cursor` holds the sweep position.
    - `MarketBrief.model` is `"deterministic"` when the text is the fallback.
    - The nightly summary gains `views_failures`, `views_cost_usd`, `verdicts_logged` and `marks_added`.
