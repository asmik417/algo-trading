# Frontend tasks (today)

Work from `frontend/`. The backend is being built in parallel, so **start on mocks** (`VITE_USE_MOCKS=true`) and switch to the live API when `http://localhost:8000/api/v1/health` answers. Every type comes from `docs/API_CONTRACT.md`; copy the TypeScript block there into `src/types/api.ts` unchanged.

## Look and feel
Clean, light, Groww-like: white cards on a `#f6f7f9` background, 8px radius, one accent green `#00b386` for positive and primary actions, red `#eb5b3c` for negative, slate greys for text. Dark mode is optional and comes last. Dense tables with sticky headers, numbers right-aligned and tabular (`font-variant-numeric: tabular-nums`). Signal badges: Early Setup green, Developing amber, Breakout Confirmed blue, Extended orange, Weak grey. Never show a raw `null`; show "—".

## Step 0 — scaffold (20 min)
`npm create vite@latest . -- --template react-ts`, add Tailwind, `@tanstack/react-query`, `react-router-dom`, `axios`, `recharts`, `lucide-react`, `clsx`, `date-fns`. `vite.config.ts` proxies `/api` to `http://localhost:8000`. Prettier + ESLint defaults. Create the folder layout from `docs/ARCHITECTURE.md`.

## Step 1 — API layer + mocks (40 min)
- `src/api/client.ts`: axios instance with `baseURL: '/api/v1'`, response interceptor that throws `{ status, detail }`.
- One module per resource with one typed function per endpoint (`profiles.ts`, `runs.ts`, `suggestions.ts`, `stocks.ts`, `positions.ts`, `reviews.ts`, `jobs.ts`).
- `src/mocks/`: realistic fixtures for every response (3 profiles, 1 done run with 8 suggestions, 2 suggestion details, 60 stock rows, 6 positions across open/due/closed, 2 reviews, stats, job status). When `import.meta.env.VITE_USE_MOCKS === 'true'`, each API function resolves the fixture after a 300 ms delay instead of calling axios. Mutations update the in-memory fixture so the UI feels real.
- `src/hooks/`: TanStack Query hooks; `useRunStatus(runId)` polls every 2 s while `queued`/`running`.
- `src/store/activeProfile.ts`: active profile id in React context + `localStorage`, defaulting to the profile with `is_active`.

## Step 2 — app shell (40 min)
`AppShell` with a 240px left sidebar: logo/title "Trade Assistant", the **AccountDropdown** at the top (active profile name + owner, dropdown lists all profiles, "Manage profiles" link to `/account`), nav items Stocks / Tracker / Loss Analysis / Account with lucide icons, and a footer showing `JobStatus.last_trading_day` ("Data as of 04 Nov 2026"). `TopBar` with the page title and a right slot for actions. Responsive down to 1024px; below that the sidebar collapses to icons.

## Step 3 — Stocks page (120 min) ← the core
Route `/stocks`, tabs **Algo Suggested** | **Explore**.

**Algo Suggested**
- `RunStatusBar`: shows the latest run (trading day, funnel counts "2,612 screened → 231 scored → 14 passed") and a **Run algo now** button. While running, a progress bar with phase + `done/total` + current symbol, polling via `useRunStatus`. On `failed`, show the error.
- `SuggestedTable` columns: Rank, Stock, Signal badge, Stage, Score (bar 0-100), Price, Entry (optimal), Stop, Target, R:R, Exit by, Profit YoY, 1M %, 3M %, Vol×, and a **Track** button (disabled with "Tracking" when `is_tracked`). Row click → `StockDialog`.
- Empty state when no run: "Run the algo under *Profile name* to get suggestions."

**Explore**
- Search input (debounced 300 ms) + sort dropdown + pagination (50 per page). Columns: Stock, Close, 1D, 1W, 1M, 3M, From 52w high, Vol×, Avg turnover. Row click → `StockDialog` in "analyze" mode: calls `POST /stocks/{symbol}/analyze?profile_id=` with a loading skeleton (can take 15 s), shows the same dialog plus a **Filters** panel listing why it would / would not be suggested.

**StockDialog** (large modal, max-width 1100px, scrollable). Header: symbol, signal badge, stage, score ring, price, Track button (or "Tracked → open in Tracker"). Body in sections:
1. **Why it is listed** — `reasons.why_flagged`, `what_changed`, positives (green ticks), risks (red marks).
2. **Analysis over time** — `PriceChart` (Recharts line: close, EMA20, EMA50; volume bars below) + `ScoreBreakdown` (six pillar bars with score/max and weight) + `FundamentalsGrid` + indicators strip (RSI, MACD, trend, ATR).
3. **When and at what price to buy** — three entry levels as cards (Aggressive / Optimal / Conservative) + `timing_note`.
4. **Planned exit** — Target, Stop-loss, Horizon (days) and planned exit date + `exit_note`.
5. Disclaimer line in muted italic.
Track action → `POST /positions` then toast "Tracking KPITTECH with ₹10,000" and update `is_tracked`.

## Step 4 — Tracker page (90 min)
Route `/tracker`.
- `StatsRow`: Win rate, Total P&L, Avg gain / Avg loss, Open / Due / Closed counts, Pending reviews (click → `/losses`), Extensions helped/hurt. From `GET /profiles/{id}/stats`.
- Tabs Open | Due | Closed | All. `PositionsTable` columns: Stock, Opened, Entry, Qty, Invested, Last close, Value, P&L (₹ and %, coloured), Target, Stop, Exit by, Days left, Status badge (due = amber pulse), Actions.
- Row click → `PositionDrawer` (right side): header with P&L, `MarksChart` (value over time with target/stop reference lines and a vertical line at `original_exit_date`), benchmark line "Nifty 50 since open: +2.1 %", `EventsTimeline` (every event with reason text), and actions: **Extend**, **Shorten**, **Close now**, **Add note**. `ExtendDialog`/`ShortenDialog`: date picker + required reason textarea (min 10 chars). `CloseDialog`: required reason.
- A **Run daily update** button in the TopBar (calls `POST /jobs/daily-update`, then refetches after 3 s) with last-run time from `GET /jobs/status`.

## Step 5 — Loss Analysis page (60 min)
Route `/losses`.
- Top: `TagSummary` — horizontal bar list of tag counts + total losses / reviewed / avg loss.
- Left: `PendingLossList` (closed losing positions without a review) — each card: symbol, loss ₹ / %, close reason, days held, **Review** button.
- `ReviewForm` (dialog or inline): tag multi-select chips from `GET /reviews/tags`, Mistakes, Lesson, "What should change in the algo or my parameters" textareas, Save → `POST /positions/{id}/review`.
- Right: `ReviewedList` — expandable cards showing the review; Edit → `PUT /reviews/{id}`.

## Step 6 — Account page (60 min)
Route `/account`.
- `ProfileList` on the left: cards for each profile (name, owner, summary, Active badge), **New profile**, **Activate**, **Delete** (confirm).
- `ProfileForm` on the right, generated from `GET /profiles/param-spec`: one `ParamSection` card per section with the section help text; field renderers by `type` (number/int → input with min/max/step; bool → switch; select → dropdown; multiselect → chip toggles). `WeightsEditor` for the "Scoring weights" section shows a live total and turns red when ≠ 100. Save → `PUT`; show backend validation `detail` under the form.

## Step 7 — polish (remaining time)
Toasts for every mutation, skeleton loaders, empty states, error boundary, keyboard close on dialogs, number formatting helpers (`₹1,23,456.00` Indian grouping, `+4.2 %`), README.

## Definition of done
- All four pages work end to end against mocks, then against the live backend with `VITE_USE_MOCKS=false`.
- No TypeScript errors, `npm run build` passes.
- `frontend/README.md` explains install, run, mocks flag, and the folder layout in under a page.
