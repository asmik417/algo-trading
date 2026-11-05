"""Step 2 checks on the SQLAlchemy models: every table in docs/DATA_MODEL.md exists, and deletes cascade.
Runs against the throwaway database from conftest.py.
"""
import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError

from app.db.session import SessionLocal, engine, init_db
from app.models import LossReview, Position, PositionEvent, PositionMark, Profile, Suggestion, SuggestionRun

EXPECTED_TABLES = {
    "profiles", "suggestion_runs", "suggestions", "positions",
    "position_events", "position_marks", "loss_reviews", "app_meta",
}


@pytest.fixture()
def db():
    init_db()
    s = SessionLocal()
    yield s
    s.rollback()
    for model in (LossReview, PositionMark, PositionEvent, Position, Suggestion, SuggestionRun, Profile):
        s.query(model).delete()
    s.commit()
    s.close()


def _graph(db) -> Profile:
    p = Profile(name="Cascade test", owner="Roshan", params_json="{}", is_active=True)
    db.add(p)
    db.flush()
    run = SuggestionRun(profile_id=p.id, trading_day="2026-11-04", status="done")
    db.add(run)
    db.flush()
    sug = Suggestion(run_id=run.id, profile_id=p.id, symbol="KPITTECH", trading_day="2026-11-04", rank=1, score=78.4,
                     stage="Quiet Accumulation", signal="🟢 Early Setup", price=1234.5, entry_aggressive=1234.5,
                     entry_optimal=1210.0, entry_conservative=1180.0, stop_loss=1150.0, target=1400.0, risk_reward=2.0,
                     horizon_days=50, planned_exit_date="2027-01-16")
    db.add(sug)
    db.flush()
    pos = Position(profile_id=p.id, suggestion_id=sug.id, symbol="KPITTECH", opened_on="2026-11-04", entry_price=1234.5,
                   qty=8, invested=9876.0, capital=10000.0, original_exit_date="2027-01-16",
                   planned_exit_date="2027-01-16", status="closed", pnl=-500.0, pnl_pct=-5.06)
    db.add(pos)
    db.flush()
    db.add_all([
        PositionEvent(position_id=pos.id, event_date="2026-11-04", event_type="open", price=1234.5),
        PositionMark(position_id=pos.id, mark_date="2026-11-04", close=1234.5, value=9876.0, pnl=0.0, pnl_pct=0.0),
        LossReview(position_id=pos.id, reasons_json='["other"]', reviewed_on="2026-11-05"),
    ])
    db.commit()
    return p


def test_all_tables_created(db):
    assert EXPECTED_TABLES <= set(inspect(engine).get_table_names())


def test_deleting_profile_cascades_everything(db):
    p = _graph(db)
    db.delete(p)
    db.commit()
    for model in (SuggestionRun, Suggestion, Position, PositionEvent, PositionMark, LossReview):
        assert db.scalars(select(model)).first() is None, model.__name__


def test_deleting_run_keeps_position_but_unlinks_suggestion(db):
    p = _graph(db)
    db.query(SuggestionRun).filter_by(profile_id=p.id).delete()  # DB-level cascade (ON DELETE)
    db.commit()
    db.expire_all()
    pos = db.scalars(select(Position)).one()
    assert pos.suggestion_id is None


def test_one_mark_per_position_per_day(db):
    p = _graph(db)
    pos = db.scalars(select(Position).where(Position.profile_id == p.id)).one()
    db.add(PositionMark(position_id=pos.id, mark_date="2026-11-04", close=1.0, value=1.0, pnl=0.0, pnl_pct=0.0))
    with pytest.raises(IntegrityError):
        db.commit()
