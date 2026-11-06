# Architecture

Two independently runnable apps in one repo, talking over a versioned JSON API.

```
ai_trade_assistant/
├── CLAUDE.md                 rules for every agent
├── docs/                     product, architecture, API contract, data model, task lists
├── backend/                  FastAPI + SQLAlchemy + the scoring engine (Python 3.14)
├── frontend/                 React 18 + TypeScript + Vite + Tailwind
├── venv/                     shared Python virtualenv (repo root)
└── _legacy/                  the old Streamlit prototype, kept for reference only
```

## Stack and why

| Layer | Choice | Why |
|---|---|---|
| API | FastAPI, Pydantic v2 | Same stack as the team's HRMS project; auto docs at `/docs`. |
| DB | SQLite via SQLAlchemy 2.0, `DATABASE_URL` configurable | Zero setup today; switch to Postgres by changing one env var. |
| Scheduler | APScheduler inside the API process | One nightly job; no extra infra. |
| Market data | NSE bhavcopy (free, full market) + yfinance (fundamentals, shortlist only) | Already proven in the prototype. Swappable behind `engine/data/`. |
| Narration | Anthropic API (`NARRATION_MODEL`, default claude-opus-5-5) via `engine/agents/` | Only narrates computed numbers; deterministic fallback text if the call fails. |
| Frontend | React + TS + Vite + Tailwind + TanStack Query + React Router + Recharts | Fast to build, easy to read, standard. |

## Backend layout

```
backend/
├── app/
│   ├── main.py                 app factory: CORS, routers, DB init, scheduler start
│   ├── core/
│   │   ├── config.py           Settings: API host/port, CORS origins, re-exports engine config
│   │   └── logging.py
│   ├── db/
│   │   ├── base.py             DeclarativeBase
│   │   └── session.py          engine, SessionLocal, get_db dependency, init_db()
│   ├── models/                 SQLAlchemy tables (see docs/DATA_MODEL.md)
│   │   ├── profile.py
│   │   ├── suggestion.py       SuggestionRun, Suggestion
│   │   ├── position.py         Position, PositionEvent, PositionMark
│   │   ├── review.py           LossReview
│   │   └── meta.py             AppMeta (key/value)
│   ├── schemas/                Pydantic request/response models, mirror docs/API_CONTRACT.md
│   ├── services/               all business logic; routers stay thin
│   │   ├── market_data.py      builds/caches the NSE panel; latest trading day; price lookup
│   │   ├── profile_service.py
│   │   ├── suggestion_service.py   runs the algo for a profile, persists run + suggestions
│   │   ├── plan_service.py     entry / stop / target / horizon rules (deterministic)
│   │   ├── explore_service.py  universe table, search, single-stock detail
│   │   ├── analysis_service.py builds the "SuggestionDetail" shape (chart, breakdown, narration)
│   │   ├── tracker_service.py  open / mark / extend / shorten / close / stats
│   │   ├── backtest_service.py runs a backtest in the background, persists results
│   │   ├── review_service.py   loss reviews and tag summaries
│   │   └── run_registry.py     in-memory status of background runs
│   ├── api/v1/                 one router per resource; `router.py` aggregates them
│   ├── engine/                 PURE scoring code (moved from the prototype; no DB/HTTP)
│   │   ├── config.py           thresholds, weights defaults, cache dirs, DB path
│   │   ├── params.py           ScreenParams + PARAM_SPEC (drives the Account form)
│   │   ├── data/               nse_universe (bhavcopy), fetcher (yfinance), indicators
│   │   ├── scoring/            six pillars, engine.evaluate(), stage, signal
│   │   ├── scanner/            the old two-stage funnel (reference; superseded by suggestion_service)
│   │   ├── backtest/           pure replay + simulation + loss-pattern tagging (no DB/HTTP)
│   │   └── agents/             LLM narration (emerging_explainer) and legacy agents
│   └── jobs/
│       └── daily_update.py     refresh panel → mark positions → close/due → record meta
├── scripts/                    CLI entry points (run_daily_update.py, seed_profiles.py, analyze_cli.py)
├── tests/
├── data/                       SQLite file + caches (gitignored)
├── logs/
├── requirements.txt
└── .env / .env.example
```

Flow for a suggestion run:

```
POST /profiles/{id}/runs
  └─ run_registry.start() → background thread
       ├─ market_data.get_panel()                    (bhavcopy, cached per day on disk)
       ├─ stage 1: rank whole universe by readiness   (engine.scanner._readiness_heuristic)
       ├─ stage 2: fetch fundamentals for top N        (engine.data.fetcher, cached per trading day)
       ├─ engine.scoring.engine.evaluate(weights=profile weights)
       ├─ apply profile hard filters (P/E, ROE, RSI, run-up …)
       ├─ plan_service.build_plan() per survivor
       └─ persist SuggestionRun + Suggestion rows; registry.status = done
```

**Caching rule:** fundamentals fetched for a (trading_day, symbol) are pickled under `data/cache/fundamentals/`. Re-running with different weights or filters must not refetch; it re-scores from cache. This makes parameter tuning feel instant after the first run of the day.

## Frontend layout

```
frontend/
├── index.html
├── package.json, vite.config.ts (proxy /api → :8000), tailwind.config.ts, tsconfig.json
└── src/
    ├── main.tsx, App.tsx, router.tsx
    ├── api/                client.ts (axios base), profiles.ts, runs.ts, suggestions.ts,
    │                       stocks.ts, positions.ts, reviews.ts, jobs.ts   (one function per endpoint)
    ├── types/              api.ts — TS types copied from docs/API_CONTRACT.md
    ├── mocks/              JSON fixtures matching the contract; used when VITE_USE_MOCKS=true
    ├── store/              activeProfile.ts (persisted in localStorage)
    ├── hooks/              useProfiles, useSuggestions, useRunStatus (polling), usePositions …
    ├── lib/                format.ts (₹, %, dates), colors.ts (signal/stage colours)
    ├── components/
    │   ├── layout/         AppShell, Sidebar, AccountDropdown, TopBar, PageHeader
    │   ├── ui/             Button, Card, Badge, Dialog, Drawer, Tabs, Table, Input, Select,
    │   │                   Textarea, Skeleton, EmptyState, Stat
    │   ├── stocks/         SuggestedTable, ExploreTable, StockDialog, ReasonsPanel, PlanPanel,
    │   │                   PriceChart, ScoreBreakdown, FundamentalsGrid, RunStatusBar
    │   ├── tracker/        StatsRow, PositionsTable, PositionDrawer, MarksChart, EventsTimeline,
    │   │                   ExtendDialog, CloseDialog
    │   ├── losses/         PendingLossList, ReviewForm, ReviewedList, TagSummary
    │   └── account/        ProfileList, ProfileForm, ParamSection, WeightsEditor
    └── pages/              StocksPage, TrackerPage, LossesPage, AccountPage
```

Routes: `/stocks` (default), `/tracker`, `/losses`, `/account`. The sidebar shows the four modules and the **account dropdown** (active profile) at the top; every page reads the active profile from the store.

## Daily monitoring

`jobs/daily_update.py` runs at 18:30 IST on weekdays via APScheduler and can be triggered by `POST /api/v1/jobs/daily-update` or `python scripts/run_daily_update.py`. It is idempotent per trading day.

## Non-goals today

Auth, multi-tenant, broker orders, websockets. Polling every 2 s on run status is fine.
