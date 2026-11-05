"""Loss Analysis endpoints: reason tags, a profile's losses (pending + reviewed), create/edit a review, tag summary.
Thin router: rules live in services/review_service.py.
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.review import LossesResponse, LossSummary, Review, ReviewBody, ReviewTag
from app.services import review_service

router = APIRouter(tags=["reviews"])


@router.get("/reviews/tags", response_model=list[ReviewTag])
def list_tags():
    return review_service.tags()


@router.get("/profiles/{profile_id}/losses", response_model=LossesResponse)
def list_losses(profile_id: int, db: Session = Depends(get_db)):
    return review_service.losses(db, profile_id)


@router.get("/profiles/{profile_id}/losses/summary", response_model=LossSummary)
def loss_summary(profile_id: int, db: Session = Depends(get_db)):
    return review_service.summary(db, profile_id)


@router.post("/positions/{position_id}/review", response_model=Review, status_code=status.HTTP_201_CREATED)
def create_review(position_id: int, body: ReviewBody, db: Session = Depends(get_db)):
    r = review_service.create_review(db, position_id, body.reasons, body.mistakes, body.lesson, body.algo_change)
    return review_service.to_schema(r)


@router.put("/reviews/{review_id}", response_model=Review)
def update_review(review_id: int, body: ReviewBody, db: Session = Depends(get_db)):
    r = review_service.update_review(db, review_id, body.reasons, body.mistakes, body.lesson, body.algo_change)
    return review_service.to_schema(r)
