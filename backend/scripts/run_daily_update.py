"""CLI: run the daily monitoring job once (refresh NSE data, mark every paper position) and print the summary.
Usage from backend/: ../venv/bin/python scripts/run_daily_update.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import init_db  # noqa: E402
from app.jobs.daily_update import run_daily_update  # noqa: E402


def main() -> int:
    init_db()
    summary = run_daily_update()
    if summary is None:
        print("Daily update is already running elsewhere; nothing done.")
        return 1
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
