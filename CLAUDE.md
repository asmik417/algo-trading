# AI Trade Assistant — working rules for every agent in this repo

This project is built by three Claude sessions working in parallel:

| Role | Owns | Reads first |
|---|---|---|
| **Guide / architect** (Fable) | `docs/`, `CLAUDE.md`, reviews, contract changes | everything |
| **Backend coder** (Opus) | `backend/` | `docs/ARCHITECTURE.md`, `docs/API_CONTRACT.md`, `docs/DATA_MODEL.md`, `docs/TASKS_BACKEND.md` |
| **Frontend coder** (Opus) | `frontend/` | `docs/ARCHITECTURE.md`, `docs/API_CONTRACT.md`, `docs/TASKS_FRONTEND.md` |

The product spec is in `docs/PRODUCT.md`. Read it before anything else so you know *why* each screen exists.

## Hard rules

1. **`docs/API_CONTRACT.md` is the single source of truth** for every request and response. Backend implements it exactly; frontend types mirror it exactly. If you need a change, do not improvise: add a note under "Proposed changes" at the bottom of that file and tell the user, who relays it to the guide.
2. **Stay inside your folder.** Backend never edits `frontend/`, frontend never edits `backend/`. Neither edits `docs/` except the "Proposed changes" section.
3. **The scoring engine (`backend/app/engine/`) is pure.** No database, no HTTP, no FastAPI imports inside it. Services call the engine; the engine never calls services.
4. **The LLM never computes.** Every number shown to the user comes from deterministic code. The model turns computed numbers into readable text, and in the Analyst view it may reason over an evidence pack and give an opinion with a confidence, shown separately from the rules verdict and scored on the scorecard. It never changes a score, level or date, and every number it writes must exist in the evidence it was given (audited automatically).
5. **Paper money only.** There is no broker integration in this phase. Do not add order placement.
6. **No silent fabrication.** If data for a stock is missing, show "unavailable" and skip that component; never fill in 0 or a made-up value.
7. **Never delete files you did not create** this session. Move them to `_legacy/` instead.
8. **Do not commit or push** unless the user asks. `git init` has not been run yet; the user decides when.
9. Keep `backend/.env` secrets out of code, logs and responses.

## Running things

```bash
# backend (from backend/)
../venv/bin/pip install -r requirements.txt
../venv/bin/uvicorn app.main:app --reload --port 8000
../venv/bin/python -m pytest tests -q

# frontend (from frontend/)
npm install
npm run dev          # http://localhost:4820, proxies /api -> http://localhost:8000
```

The Python venv lives at the repo root (`venv/`), shared with the old prototype. Python is 3.14.

## Style

- Backend: Python 3.12+ typing, Pydantic v2 schemas, SQLAlchemy 2.0, one service per domain, thin routers. Docstring at the top of every module saying what it is for in two lines.
- Frontend: React 18 + TypeScript strict, Vite, Tailwind, TanStack Query for all server state, one API module per resource, no `any`.
- Names are plain English. A new team member must understand a folder from its name alone.
- Money is Indian rupees; format as `₹12,345.60`. Dates in the API are ISO `YYYY-MM-DD`; the UI shows `05 Nov 2026`.
