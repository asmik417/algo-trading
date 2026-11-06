"""Maintenance: re-fetch every cached fundamentals bundle without `info` for one day (e.g. after Yahoo rate-limited
a bulk fetch). Recovered bundles replace the empty file; bundles still empty after retries are removed, since an
empty bundle must never be cached. Usage from backend/:
    ../venv/bin/python scripts/refetch_empty_fundamentals.py 2026-11-05
"""
import os
import pickle
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.engine import config as engine_config  # noqa: E402
from app.engine.data import fetcher  # noqa: E402
from app.services.suggestion_service import has_info, save_fundamentals  # noqa: E402


def refetch_day(day: str, fetch=fetcher.fetch_fundamental_bundle) -> dict:
    folder = os.path.join(engine_config.FUNDAMENTALS_CACHE_DIR, day)
    counts = {"cached": 0, "empty": 0, "recovered": 0, "still_empty": 0, "rate_limited": 0}
    if not os.path.isdir(folder):
        return counts
    names = sorted(f for f in os.listdir(folder) if f.endswith(".pkl"))
    counts["cached"] = len(names)
    empty = []
    for name in names:
        try:
            with open(os.path.join(folder, name), "rb") as f:
                ok = has_info(pickle.load(f))
        except Exception:
            ok = False
        if not ok:
            empty.append(name[:-4])
    counts["empty"] = len(empty)
    started = time.monotonic()
    for i, symbol in enumerate(empty, start=1):
        bundle = fetch(symbol, limiter=fetcher.BULK_LIMITER)
        if has_info(bundle):
            save_fundamentals(day, symbol, bundle)
            counts["recovered"] += 1
        else:
            os.remove(os.path.join(folder, f"{symbol}.pkl"))
            counts["still_empty"] += 1
            counts["rate_limited"] += bool(bundle.get("rate_limited"))
        if i % 50 == 0 or i == len(empty):
            print(f"  {i}/{len(empty)} re-fetched, {counts['recovered']} recovered, "
                  f"{time.monotonic() - started:.0f}s", flush=True)
    return counts


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    day = sys.argv[1]
    counts = refetch_day(day)
    print(f"{day}: {counts['cached']} cached bundles, {counts['empty']} empty -> {counts['recovered']} recovered, "
          f"{counts['still_empty']} still empty and removed ({counts['rate_limited']} of those still rate-limited)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
