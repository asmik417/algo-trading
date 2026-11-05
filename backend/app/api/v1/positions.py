"""Tracker endpoints: open a paper position, list/detail, extend, shorten, close, notes, and profile stats.
Thin router: all rules live in services/tracker_service.py.
"""
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.position import (ChangeExitBody, ClosePositionBody, CreatePositionBody, NoteBody, Position,
                                  PositionDetail, ProfileStats)
from app.services import tracker_service

router = APIRouter(tags=["positions"])


@router.post("/positions", response_model=Position, status_code=status.HTTP_201_CREATED)
def open_position(body: CreatePositionBody, db: Session = Depends(get_db)):
    p = tracker_service.open_position(db, body.profile_id, body.suggestion_id, body.symbol, body.capital)
    return tracker_service.to_schema(p, reviewed=False)


@router.get("/profiles/{profile_id}/positions", response_model=list[Position])
def list_positions(profile_id: int, status: str = Query("all"), db: Session = Depends(get_db)):
    return tracker_service.list_positions(db, profile_id, status)


@router.get("/positions/{position_id}", response_model=PositionDetail)
def get_position(position_id: int, db: Session = Depends(get_db)):
    return tracker_service.detail(db, position_id)


@router.post("/positions/{position_id}/extend", response_model=PositionDetail)
def extend(position_id: int, body: ChangeExitBody, db: Session = Depends(get_db)):
    tracker_service.extend(db, position_id, body.new_exit_date.isoformat(), body.reason)
    return tracker_service.detail(db, position_id)


@router.post("/positions/{position_id}/shorten", response_model=PositionDetail)
def shorten(position_id: int, body: ChangeExitBody, db: Session = Depends(get_db)):
    tracker_service.shorten(db, position_id, body.new_exit_date.isoformat(), body.reason)
    return tracker_service.detail(db, position_id)


@router.post("/positions/{position_id}/close", response_model=PositionDetail)
def close(position_id: int, body: ClosePositionBody, db: Session = Depends(get_db)):
    tracker_service.close_manual(db, position_id, body.reason)
    return tracker_service.detail(db, position_id)


@router.post("/positions/{position_id}/notes", response_model=PositionDetail)
def add_note(position_id: int, body: NoteBody, db: Session = Depends(get_db)):
    tracker_service.add_note(db, position_id, body.note)
    return tracker_service.detail(db, position_id)


@router.get("/profiles/{profile_id}/stats", response_model=ProfileStats)
def profile_stats(profile_id: int, db: Session = Depends(get_db)):
    return tracker_service.stats(db, profile_id)
