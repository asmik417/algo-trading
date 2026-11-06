"""The nightly brain job (docs/BRAIN_PLAN.md -> Pipeline): pull sources, market brief, an evidence pack and an
analyst view per followed stock, then log verdicts and mark old ones. One run at a time; idempotent per day.
"""
import json
import threading
from datetime import date

from sqlalchemy import select

from app.core.clock import utc_now_iso
from app.core.logging import get_logger
from app.core.redaction import redact
from app.db.session import SessionLocal
from app.engine.data.sources import (SOURCES, announcements, common, deals, global_cues, insider, market, news, results,
                                     shareholding)
from app.models import BrainJob, PickList, Position, Shareholding, Suggestion, SuggestionRun
from app.engine import config as engine_config
from app.services import (analyst_service, evidence_service, market_brief_service, market_data, profile_service,
                          scorecard_service, source_service)

log = get_logger(__name__)

MODULES = {"announcements": announcements, "deals": deals, "insider": insider, "shareholding": shareholding,
           "market": market, "global_cues": global_cues, "news": news, "results": results}
SHAREHOLDING_BACKFILL_DAYS = 95   # first ever pull: one quarter of filings, so every stock has a latest pattern
_lock = threading.Lock()


def is_running() -> bool:
    return _lock.locked()


def followed_symbols(db) -> list[str]:
    """Stocks the brain follows: every pick list, the latest finished full run of each profile, open positions."""
    symbols: set[str] = set()
    for pl in db.scalars(select(PickList)):
        symbols.update(json.loads(pl.symbols_json or "[]"))
    latest = {}
    for run in db.scalars(select(SuggestionRun).where(SuggestionRun.kind == "full", SuggestionRun.status == "done")):
        if run.profile_id not in latest or run.id > latest[run.profile_id]:
            latest[run.profile_id] = run.id
    if latest:
        symbols.update(db.scalars(select(Suggestion.symbol).where(Suggestion.run_id.in_(latest.values()))))
    symbols.update(db.scalars(select(Position.symbol).where(Position.status.in_(("open", "due")))))
    return sorted(symbols)


def _company_names(symbols: list[str]) -> dict[str, str]:
    by_symbol = {}
    for name, symbol in common.known_names().items():
        by_symbol.setdefault(symbol, name.title())
    return {s: by_symbol.get(s, s) for s in symbols}


def pull_source(db, source: str, day: date) -> dict:
    """Fetch, store and record one source; never raises. Returns {status, records, inserted, error}."""
    module = MODULES[source]
    try:
        if source == "shareholding" and not source_service.has_rows(db, Shareholding):
            raw = module.fetch(day, lookback_days=SHAREHOLDING_BACKFILL_DAYS)
        elif source == "news":
            raw = module.fetch(day, companies=_company_names(followed_symbols(db)))
        else:
            raw = module.fetch(day)
        warnings = [r.get("note") for r in raw if r.get("key") == "_warning"]
        records = [r for r in raw if r.get("key") != "_warning"]
        inserted = source_service.persist(db, source, day, records)
        status = "ok" if records else "empty"
        error = "; ".join(w for w in warnings if w) or None
    except Exception as e:  # a failing source never blocks the others
        db.rollback()
        log.warning("Nightly brain: %s for %s failed: %s", source, day, e)
        records, inserted, status, error = [], 0, "failed", redact(str(e) or type(e).__name__)[:500]
    source_service.record_pull(db, source, day, status, len(records), inserted, error)
    return {"status": status, "records": len(records), "inserted": inserted, "error": error}


def build_brief(db, day: date) -> dict:
    """The market brief step; never raises. Returns {regime, audited} or {error}."""
    try:
        brief = market_brief_service.build(db, day.isoformat())
        row_audited = market_brief_service.is_audited(db, day.isoformat())
        return {"regime": brief["regime"], "audited": row_audited}
    except Exception as e:
        db.rollback()
        log.exception("Nightly brain: market brief for %s failed", day)
        return {"error": redact(str(e) or type(e).__name__)[:300]}


def build_packs(db, day: date) -> dict:
    """An evidence pack per followed stock; one failing stock never stops the others."""
    built, failed, packed = 0, {}, []
    try:
        context = market_brief_service.context(db, day.isoformat())
    except Exception:
        log.exception("Nightly brain: market context for %s failed", day)
        context = None
    for symbol in followed_symbols(db):
        try:
            evidence_service.build(db, symbol, day.isoformat(), fetch_missing=True, brief_context=context)
            built += 1
            packed.append(symbol)
        except Exception as e:
            db.rollback()
            failed[symbol] = redact(str(e) or type(e).__name__)[:200]
    if failed:
        log.info("Nightly brain: no evidence pack for %s", failed)
    return {"packs_built": built, "packs_failed": failed, "packed": packed}


def build_views(db, day: date, symbols: list[str]) -> dict:
    """An analyst view per packed stock under the active strategy (cached views cost nothing), at most
    ANALYST_MAX_VIEWS_PER_NIGHT new ones. A failing view never stops the others."""
    built, failed, cost, new_calls = 0, {}, 0.0, 0
    try:
        profile_id = profile_service.get_active(db).id
    except Exception:
        return {"views_built": 0, "views_failed": 0, "views_failures": {"*": "no active strategy"}, "views_cost_usd": 0.0}
    for symbol in symbols:
        if analyst_service.view_for(db, symbol, day.isoformat(), profile_id):
            built += 1
            continue
        if new_calls >= engine_config.ANALYST_MAX_VIEWS_PER_NIGHT:
            failed[symbol] = "skipped: nightly limit reached"
            continue
        new_calls += 1
        try:
            view = analyst_service.analyze(db, symbol, day.isoformat(), profile_id)
            built += 1
            cost += analyst_service.cost_of(db, view["id"])[0] or 0.0
        except Exception as e:
            db.rollback()
            failed[symbol] = redact(str(e) or type(e).__name__)[:200]
    return {"views_built": built, "views_failed": len(failed), "views_failures": failed,
            "views_cost_usd": round(cost, 4)}


def score(db) -> dict:
    """Log every new rules verdict, then mark logged verdicts that have reached 20/40/60 sessions."""
    try:
        logged = scorecard_service.log_rules_verdicts(db)
        marks = scorecard_service.mark_all(db)
        return {"verdicts_logged": logged, "marks_added": marks}
    except Exception as e:
        db.rollback()
        log.exception("Nightly brain: scorecard step failed")
        return {"verdicts_logged": 0, "marks_added": 0, "score_error": redact(str(e))[:200]}


def start_job(day: date | None = None) -> BrainJob | None:
    """Create the job row; None if a run is already going."""
    if is_running():
        return None
    with SessionLocal() as db:
        job = BrainJob(day=day.isoformat() if day else None, status="queued")
        db.add(job)
        db.commit()
        return job


def run(job_id: int, day: date | None = None) -> dict | None:
    """Run the job in this thread. None if another run holds the lock."""
    if not _lock.acquire(blocking=False):
        with SessionLocal() as db:  # lost the race to another run: say so instead of leaving it queued
            job = db.get(BrainJob, job_id)
            if job is not None and job.status == "queued":
                job.status, job.error, job.finished_at = "failed", "Another nightly brain run was already going.", utc_now_iso()
                db.commit()
        return None
    try:
        with SessionLocal() as db:
            job = db.get(BrainJob, job_id)
            day = day or date.fromisoformat(market_data.panel_day())
            job.day, job.status, job.started_at = day.isoformat(), "running", utc_now_iso()
            db.commit()
            try:
                summary = {"sources": {s: pull_source(db, s, day) for s in SOURCES}}
                summary["brief"] = build_brief(db, day)
                summary.update(build_packs(db, day))
                summary.update(build_views(db, day, summary.pop("packed", [])))
                summary.update(score(db))
                job.summary_json, job.status = json.dumps(summary), "done"
                log.info("Nightly brain %s for %s: %s; brief %s; %d packs (%d failed); %d views (%d failed, $%s); "
                         "%d verdicts logged, %d marks", job_id, day,
                         {s: (v["status"], v["records"]) for s, v in summary["sources"].items()},
                         summary["brief"], summary["packs_built"], len(summary["packs_failed"]), summary["views_built"],
                         summary["views_failed"], summary["views_cost_usd"], summary["verdicts_logged"],
                         summary["marks_added"])
                return summary
            except Exception as e:
                log.exception("Nightly brain %s failed", job_id)
                job.status, job.error = "failed", redact(f"{type(e).__name__}: {e}")[:500]
                return None
            finally:
                job.finished_at = utc_now_iso()
                db.commit()
    finally:
        _lock.release()


def start_in_background(day: date | None = None) -> int | None:
    job = start_job(day)
    if job is None:
        return None
    threading.Thread(target=run, args=(job.id, day), name=f"nightly-brain-{job.id}", daemon=True).start()
    return job.id


def status(db) -> dict | None:
    """The `brain` block of GET /jobs/status; None until the job has run once."""
    job = db.scalar(select(BrainJob).where(BrainJob.day.is_not(None)).order_by(BrainJob.id.desc()).limit(1))
    if job is None:
        return {"running": True, "last_day": None, "sources": [], "packs_built": 0, "views_built": 0,
                "views_failed": 0} if is_running() else None
    summary = json.loads(job.summary_json or "{}")
    return {"running": is_running(), "last_day": job.day, "sources": source_service.statuses(db, job.day),
            "packs_built": summary.get("packs_built", 0), "views_built": summary.get("views_built", 0),
            "views_failed": summary.get("views_failed", 0)}
