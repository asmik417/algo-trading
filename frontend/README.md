# Frontend — AI Trade Assistant UI

React 18 + TypeScript (strict) + Vite + Tailwind, with TanStack Query for all server state, React Router 7 and Recharts 3. It talks to the backend at `/api/v1`; Vite proxies that to `http://localhost:8000`. Read `../docs/PRODUCT.md`, `../docs/API_CONTRACT.md` and `../docs/TASKS_FRONTEND.md` first.

## Install and run
```bash
npm install
npm run dev        # http://localhost:4820  (start the backend first: see ../CLAUDE.md)
npm run build      # type-check + production build
npm run lint       # ESLint
npm run format     # Prettier
```

## Mock mode
`.env` holds `VITE_USE_MOCKS`:

| Value | Behaviour |
|---|---|
| `false` | Real calls to the backend. This is the normal setting. |
| `true` | Every API function resolves a fixture from `src/mocks/` after 300 ms; no backend needed. Mutations change an in-memory copy, so tracking, extending, closing and reviewing all behave like the real thing. A "Mock data" pill shows in the sidebar. |

Mock mode behaves like the real backend about login too: sign in as `roshan` / `demo` (shown on the login page); the mock session survives a reload.

The flag is global (not per resource). Restart `npm run dev` after changing `.env`. Mock parameters mirror a snapshot of the live `GET /profiles/param-spec` (`src/mocks/paramSpec.ts`).

## Login
One user. The backend reads `APP_USERNAME` / `APP_PASSWORD` from `backend/.env` and sets an HttpOnly `session` cookie (30 days). On load the app calls `GET /auth/me` behind a splash screen; signed-out visitors go to `/login`, and any 401 from the API signs you out and returns you there. **Sign out** is at the bottom of the sidebar.

## Pages
`/login`, then `/stocks` (Algo Suggested, Explore and My Picks, all opening the same stock dialog), `/tracker`, `/holdings` (placeholder for future live trading; no API calls), `/losses`, `/backtest` (new backtest, past backtests, Compare) with results at `/backtest/:id`, `/strategies`.

**My Picks** (`/stocks?tab=picks&run=ID`): pick up to 50 symbols (type-ahead, chips, or paste a comma/space-separated list), press Analyse, and the watchlist run is polled like a full run. Results show a Verdict (Passes / Fails + first failure); unknown symbols get an "Error: …" row. "Previous analyses" reopens earlier lists for the active strategy. The active strategy is chosen from the "Active strategy" dropdown in the sidebar and kept in `localStorage`. `/tracker?position=ID` opens that position's drawer.

Wording: the UI says **Strategy** (and Strategies); the API and the data layer (`useProfiles`, `Profile`) still say profile. The API's `owner` field is never shown; new strategies are created without it (the backend defaults it to the signed-in username).

## Folder layout (`src/`)
```
api/          axios client (sends the session cookie, reports 401s) + one module per resource, one typed function per endpoint
types/        api.ts = the contract's TypeScript block, copied verbatim (never edit by hand); ui.ts = frontend-only query types
mocks/        fixtures + an in-memory fake backend (db.ts) that mirrors each endpoint, errors included
hooks/        TanStack Query hooks and the query-key list; useRunStatus polls every 2 s
store/        auth (who is signed in) and activeProfile (the active strategy; context + localStorage)
lib/          format.ts (₹ Indian grouping, %, dates; missing data is always "—"), colors.ts, labels.ts, dates.ts
components/   layout/ ui/ stocks/ tracker/ losses/ strategies/   (one folder per screen area; ui/ = shared primitives)
pages/        one file per route
```

## Rules this code follows
- `src/types/api.ts` mirrors `../docs/API_CONTRACT.md` exactly. A needed change goes under "Proposed changes" in that file, not into the types.
- Never show `null`; unavailable values render as "—", and a scoring pillar with no data says "Unavailable — not scored" (never 0).
- Paper money only: tracking always sends `{ profile_id, suggestion_id }`.
- My Picks results are `WatchlistHit | WatchlistMiss`; narrow with `isMiss()` (`lib/watchlist.ts`) and read only `symbol` and `error` on a miss.
- The Strategies form is generated from `param-spec` (types, limits, options); the only name it knows is the reserved section `Scoring weights`.
