"""Nightly brain job, part 1 (pull sources): insert-only storage, source_pulls statuses, a failing source never
blocking the others, the one-off shareholding backfill, POST /jobs/nightly-brain and the brain block of
GET /jobs/status. Pullers are faked; no network.
"""
import threading
from datetime import date

import pytest

from app.db.session import SessionLocal
from app.engine.data.sources import SOURCES
from app.jobs import nightly_brain
from app.models import Announcement, MarketContextRow, QuarterlyResult, SourcePull

DAY = date(2026, 11, 5)

ANN = {"key": "ann:1:MPHASIS", "symbol": "MPHASIS", "date": "2026-11-05", "at": "2026-11-05T23:54:22",
       "kind": "Press Release", "title": "Q2 results", "url": "https://x/a.pdf", "source": "nse"}
RESULT = {"key": "nse:210973", "symbol": "MPHASIS", "period_end": "2026-09-30", "filed_on": "2026-11-05",
          "filed_at": "2026-11-05T23:54:22", "nature": "Consolidated", "revenue": 4.58e10, "ebitda": 8.29e9,
          "net_profit": 5.61e9, "eps": 29.39, "margin_pct": 18.1}
VIX = {"key": "vix", "date": "2026-11-05", "value": 17.18, "unit": "points"}


class Fake:
    def __init__(self, rows=None, error=None):
        self.rows, self.error, self.calls = rows or [], error, []

    def fetch(self, day, **kw):
        self.calls.append(kw)
        if self.error:
            raise self.error
        return list(self.rows)


@pytest.fixture()
def fakes(client, monkeypatch):
    mods = {s: Fake() for s in SOURCES}
    mods["announcements"].rows = [ANN]
    mods["results"].rows = [RESULT]
    mods["market"].rows = [VIX, {"key": "_warning", "date": "2026-11-05", "note": "indices: intraday"}]
    mods["deals"].error = RuntimeError("NSE publishes deals for the latest session only")
    monkeypatch.setattr(nightly_brain, "MODULES", mods)
    monkeypatch.setattr(nightly_brain.market_data, "panel_day", lambda: DAY.isoformat())
    return mods


def _run(day=None):
    job = nightly_brain.start_job(day)
    return job.id, nightly_brain.run(job.id, day)


def test_pull_step_statuses_and_insert_only(fakes):
    job_id, summary = _run()
    s = summary["sources"]
    assert s["announcements"] == {"status": "ok", "records": 1, "inserted": 1, "error": None}
    assert s["deals"]["status"] == "failed" and "latest session only" in s["deals"]["error"]   # others still ran
    assert s["insider"] == {"status": "empty", "records": 0, "inserted": 0, "error": None}
    assert s["market"] == {"status": "ok", "records": 1, "inserted": 1, "error": "indices: intraday"}
    with SessionLocal() as db:
        assert db.query(QuarterlyResult).one().filed_on == "2026-11-05"
        assert db.query(MarketContextRow).one().metric == "vix"
        assert {p.source: p.status for p in db.query(SourcePull)}["deals"] == "failed"

    fakes["announcements"].rows = [ANN, {**ANN, "key": "ann:2:MPHASIS", "title": "Investor call"}]
    _, again = _run()                                                         # same day, re-run
    assert again["sources"]["announcements"]["inserted"] == 1                 # only the new one
    with SessionLocal() as db:
        assert db.query(Announcement).count() == 2 and db.query(QuarterlyResult).count() == 1
        assert db.query(SourcePull).count() == len(SOURCES)                   # one status row per (source, day)


def test_shareholding_backfills_once_and_news_gets_followed_companies(fakes, client):
    fakes["shareholding"].rows = [{"key": "pattern:MPHASIS:2026-09-30:1", "symbol": "MPHASIS", "kind": "pattern",
                                   "filed_on": "2026-11-05", "as_of": "2026-09-30", "promoter_pct": 40.0,
                                   "public_pct": 60.0, "pledge_pct": None}]
    client.post("/api/v1/pick-lists", json={"name": "Holdings", "symbols": ["MPHASIS", "TCS"]})
    _run()
    assert fakes["shareholding"].calls[-1] == {"lookback_days": nightly_brain.SHAREHOLDING_BACKFILL_DAYS}
    assert set(fakes["news"].calls[-1]["companies"]) == {"MPHASIS", "TCS"}
    _run()
    assert fakes["shareholding"].calls[-1] == {}                              # table no longer empty: day only


def test_api_start_status_and_409(fakes, client, monkeypatch):
    assert client.get("/api/v1/jobs/status").json()["brain"] is None          # never run yet
    gate = threading.Event()
    real_pull = nightly_brain.pull_source
    monkeypatch.setattr(nightly_brain, "pull_source", lambda db, s, d: gate.wait(5) and real_pull(db, s, d))
    r = client.post("/api/v1/jobs/nightly-brain", json={"day": "2026-11-05"})
    assert r.status_code == 202 and isinstance(r.json()["job_id"], int)
    for _ in range(50):
        if nightly_brain.is_running():
            break
        threading.Event().wait(0.05)
    assert client.post("/api/v1/jobs/nightly-brain", json={}).status_code == 409
    assert client.get("/api/v1/jobs/status").json()["brain"]["running"] is True
    gate.set()
    for _ in range(100):
        if not nightly_brain.is_running():
            break
        threading.Event().wait(0.05)
    brain = client.get("/api/v1/jobs/status").json()["brain"]
    assert brain["running"] is False and brain["last_day"] == "2026-11-05"
    assert [x["source"] for x in brain["sources"]] == list(SOURCES)
    assert {x["source"]: x["status"] for x in brain["sources"]}["deals"] == "failed"
    assert (brain["packs_built"], brain["views_built"], brain["views_failed"]) == (0, 0, 0)
    assert client.post("/api/v1/jobs/nightly-brain", json={"day": "05-11-2026"}).status_code == 400
