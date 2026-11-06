# AI Trade Assistant

A paper-trading strategy lab for NSE stocks. You set the rules a trader screens on, the algo scans the whole market and suggests stocks with a buy plan and an exit plan, every pick is tracked with fake money, and the app grades its own accuracy so the rules can improve.

**No real orders are placed.** Everything is paper money. Live broker holdings and automatic buy/sell are a future module.

## What it does

| Module | What you do there |
|---|---|
| **Strategies** | Set and save the screening parameters: liquidity, fundamentals, technicals, scoring weights, holding horizon, stop and target rules. Research-backed defaults are seeded. |
| **Stocks → Algo Suggested** | Run the algo under the active strategy. Each pick shows score, stage, signal, entry levels, stop-loss, target and planned exit date. Click a row for the full analysis and reasons. |
| **Stocks → Explore** | Search every NSE stock and analyse any one of them under your rules. |
| **Stocks → My Picks** | Paste a list of symbols and analyse them together; see which pass and why the rest fail. |
| **Tracker** | Track a pick with ₹10,000 of paper money. Marked to market daily, auto-closed on stop or target, flagged when the exit date arrives. Extending or shortening requires a written reason. |
| **Loss Analysis** | Every losing position gets a tagged review: what went wrong, the lesson, and what should change in the rules. |
| **Holdings** | Placeholder for the future live-trading module. |

## How the algo works

1. **Stage 1, whole market, free.** Every NSE equity's price and volume history is built from NSE's daily bhavcopy files and ranked on chart readiness.
2. **Stage 2, shortlist.** The top chart setups get fundamentals pulled and are scored 0-100 on six pillars: earnings acceleration, fundamental quality, early price position, volume accumulation, technical setup, valuation. Weights come from the strategy.
3. **Hard filters.** P/E, ROE, debt, profit growth, RSI, 200-day EMA, run-up, volume and 52-week-high distance from the strategy.
4. **Trade plan.** Deterministic rules: three entry levels from EMAs and ATR, stop at a volatility multiple, target at a reward-to-risk ratio, holding horizon by stage.
5. **Narration.** An LLM turns the computed numbers into readable reasons. It never decides a score, price or date.

## Repository layout

```
backend/    FastAPI API + scoring engine (Python 3.14, SQLAlchemy, SQLite)
frontend/   React 18 + TypeScript + Vite + Tailwind UI
docs/       product spec, architecture, API contract, data model, task lists
_legacy/    the original Streamlit prototype, kept for reference
CLAUDE.md   working rules for the AI coding sessions that build this repo
```

Branches: `main` holds the integrated app; `backend` and `frontend` are the working branches for each side.

## Run it locally

```bash
# one-time
python3 -m venv venv && venv/bin/pip install -r backend/requirements.txt
cp backend/.env.example backend/.env     # set ANTHROPIC_API_KEY, APP_USERNAME, APP_PASSWORD, SECRET_KEY
cd frontend && npm install && cd ..

# every time (two terminals)
cd backend && ../venv/bin/uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev               # http://localhost:4820
```

API docs: http://localhost:8000/docs. Tests: `cd backend && ../venv/bin/python -m pytest tests -q`.

The first run downloads missing bhavcopy days from NSE and takes a few minutes; later runs take under a minute.

## Data sources

- Prices and volume: NSE bhavcopy (free, full market) via `jugaad-data`.
- Fundamentals: yfinance (shortlist only, cached per trading day).
- Narration: Anthropic API.

## Read next

- `docs/PRODUCT.md` for the why, vocabulary and success metrics.
- `docs/ARCHITECTURE.md` for the stack and folder layout.
- `docs/API_CONTRACT.md` for every endpoint and type.
