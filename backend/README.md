# Backend — AI Trade Assistant API

FastAPI service that runs the stock-screening algo under a profile's parameters, plans entries and exits, tracks paper positions and grades results. Read `../docs/ARCHITECTURE.md`, `../docs/API_CONTRACT.md` and `../docs/TASKS_BACKEND.md` before changing anything.

## Setup
```bash
cp .env.example .env                          # optional: ANTHROPIC_API_KEY for narrated reasons
../venv/bin/pip install -r requirements.txt
../venv/bin/python scripts/seed_profiles.py   # Roshan / Manager / MD profiles (safe to re-run)
```
First startup also creates one active "Default – Balanced" profile if there are none.

## Run
```bash
../venv/bin/uvicorn app.main:app --reload --port 8000    # API at /api/v1, docs at http://localhost:8000/docs
```
On startup the server builds the NSE panel in the background (~10 s from the disk cache; missing days are downloaded from NSE first). A run (`POST /api/v1/profiles/{id}/runs`) takes ~40 s the first time each trading day (yfinance fundamentals for the shortlist) and ~15 s after that (cached under `data/cache/fundamentals/<day>/`).

## Test
```bash
../venv/bin/python -m pytest tests -q
```
Tests never touch the network or `data/trade_assistant.db`: they use a throwaway SQLite file, synthetic price panels and a fake yfinance. `tests/test_contract_schemas.py` parses `docs/API_CONTRACT.md` and fails if any schema drifts from it.

## Daily job
Marks every open/due paper position to the latest close, closes on stop-loss or target, and flags positions *due* at their planned exit date. Missed days are caught up in order, so a stop hit on Tuesday closes at Tuesday's close even if the job only ran on Friday.
- Scheduled inside the API: Mon–Fri 18:30 Asia/Kolkata (`DAILY_JOB_HOUR`, `DAILY_JOB_MINUTE` in `.env`). If NSE has not published that day's file yet, the next run catches up.
- On demand: `POST /api/v1/jobs/daily-update`, status at `GET /api/v1/jobs/status`.
- From the shell: `../venv/bin/python scripts/run_daily_update.py`.
A file lock (`data/daily_update.lock`) guarantees only one run at a time across the API and the script.

## Login
One user, set in `.env`: `APP_USERNAME`, `APP_PASSWORD`, `SECRET_KEY`. `POST /api/v1/auth/login` sets a signed, HttpOnly, SameSite=Lax `session` cookie valid for 30 days; every route except `/health` and `/auth/*` returns 401 without it. Set `SECRET_KEY` to a long random string, otherwise a random key is generated at startup and every restart logs you out. Set `COOKIE_SECURE=1` when serving over HTTPS. Changing `APP_USERNAME` or `SECRET_KEY` invalidates existing sessions.

## Narration
The "why it was listed" text is written by Claude (`NARRATION_MODEL`, default `claude-opus-5-5`, effort `low`) from numbers the engine already computed; it never decides a score, price or date. Set `ANTHROPIC_API_KEY` in `.env` to enable it. Without a key, or if a call fails (auth, rate limit, API or network error, non-JSON reply), the deterministic template is used instead and the LLM is retried at most hourly per suggestion. Calls enable Anthropic's server-side fallback (`fallbacks="default"`), which re-runs a request on another model if the safety layer declines it; remove the `betas` and `fallbacks` lines in `app/engine/agents/base_agent.py` to turn it off.

## Layout
`api/v1/` thin routers → `services/` all logic → `engine/` pure scoring (no DB/HTTP) and `models/` SQLAlchemy tables. `jobs/` holds the daily update and its scheduler. Env switches: `DATABASE_URL`, `ENABLE_SCHEDULER=0`, `WARM_PANEL=0`.
