"""Suggestion endpoints: a profile's latest (or chosen) run with its picks, and one suggestion's full dialog.
Thin router: shapes are built in services/analysis_service.py.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.suggestion import SuggestionDetail, SuggestionsResponse
from app.services import suggestion_service

router = APIRouter(tags=["suggestions"])


@router.get("/profiles/{profile_id}/suggestions", response_model=SuggestionsResponse)
def list_suggestions(profile_id: int, run_id: str = Query("latest"), db: Session = Depends(get_db)):
    return suggestion_service.suggestions_for(db, profile_id, run_id)


@router.get("/suggestions/{suggestion_id}", response_model=SuggestionDetail)
def get_suggestion(suggestion_id: int, db: Session = Depends(get_db)):
    return suggestion_service.suggestion_detail(db, suggestion_id)
