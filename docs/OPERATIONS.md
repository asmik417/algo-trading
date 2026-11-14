# Operations Guide

## Running the backend

```bash
cd backend
../venv/bin/python -m pytest tests -q
../venv/bin/uvicorn app.main:app --reload --port 8000
```

## Running the frontend

```bash
cd frontend
npm install
npm run dev
```

## Migrations

The repository uses SQLAlchemy metadata and should grow a migration layer as models evolve. Keep migration files in `backend/migrations/` once the schema is locked.

For local work without migrations:

```bash
cd backend
../venv/bin/python -c "from app.db.session import init_db; init_db()"
```

## Backtests and paper sessions

- Use fixture-market data for reproducible runs.
- Store the strategy version, data snapshot hash, code version, seed, and risk configuration in run metadata.
- Re-run the same config with the same fixture data to confirm the run hash is unchanged.

## Pause / kill switch / recovery

- Flip the risk config `kill_switch` to halt all new order creation.
- Review the ledger, positions, and rejected orders before resuming.
- Idempotency keys and run IDs should be preserved on retried jobs to avoid duplicate fills.

## Recovery notes

- If a scheduler restarts, it must not create a second paper order for the same session or run ID.
- Reprocessing a market bar should be idempotent and should only reapply the same deterministic fill rules.
