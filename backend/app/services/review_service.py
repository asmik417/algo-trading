"""Loss Analysis: the fixed reason tags, closed losing positions awaiting review, reviews, and tag counts.
A review records why a paper trade lost and what parameter or algo change it suggests.
"""
import json
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LossReview, Position
from app.services import profile_service, tracker_service
from app.services.errors import BadInput, Conflict, NotFound

TAGS: dict[str, str] = {
    "bought_extended": "Bought when already extended",
    "stop_too_tight": "Stop-loss was too tight",
    "stop_too_wide": "Stop-loss was too wide",
    "earnings_miss": "Earnings missed expectations",
    "whole_market_fell": "Whole market fell",
    "sector_news": "Sector news",
    "company_news": "Company-specific news",
    "weak_fundamentals_missed": "Weak fundamentals the algo missed",
    "low_liquidity": "Low liquidity",
    "held_too_long": "Held too long",
    "exited_too_early": "Exited too early",
    "bad_entry_timing": "Bad entry timing",
    "other": "Other",
}


def tags() -> list[dict]:
    return [{"key": k, "label": v} for k, v in TAGS.items()]


def _clean_reasons(reasons: list[str]) -> list[str]:
    unknown = [r for r in reasons if r not in TAGS]
    if unknown:
        raise BadInput(f"Unknown reason tag(s): {', '.join(unknown)}.")
    cleaned = list(dict.fromkeys(reasons))  # dedupe, keep order
    if not cleaned:
        raise BadInput("Pick at least one reason.")
    return cleaned


def to_schema(review: LossReview) -> dict:
    p = review.position
    return {
        "id": review.id, "position_id": p.id, "symbol": p.symbol, "pnl": p.pnl, "pnl_pct": p.pnl_pct,
        "closed_on": p.closed_on, "close_reason": p.close_reason, "reasons": json.loads(review.reasons_json),
        "mistakes": review.mistakes, "lesson": review.lesson, "algo_change": review.algo_change,
        "reviewed_on": review.reviewed_on, "created_at": review.created_at,
    }


def _closed_losses(db: Session, profile_id: int) -> list[Position]:
    return list(db.scalars(select(Position).where(Position.profile_id == profile_id, Position.status == "closed",
                                                  Position.pnl < 0).order_by(Position.closed_on.desc(), Position.id.desc())))


def losses(db: Session, profile_id: int) -> dict:
    profile_service.get_profile(db, profile_id)
    rows = _closed_losses(db, profile_id)
    reviews = {r.position_id: r for r in db.scalars(select(LossReview).where(
        LossReview.position_id.in_([p.id for p in rows])))} if rows else {}
    pending = [tracker_service.to_schema(p, reviewed=False) for p in rows if p.id not in reviews]
    reviewed = sorted(reviews.values(), key=lambda r: (r.reviewed_on, r.id), reverse=True)
    return {"pending": pending, "reviewed": [to_schema(r) for r in reviewed]}


def create_review(db: Session, position_id: int, reasons: list[str], mistakes: str, lesson: str,
                  algo_change: str) -> LossReview:
    p = tracker_service.get_position(db, position_id)
    if p.status != "closed" or p.pnl is None or p.pnl >= 0:
        raise Conflict(f"Position {position_id} is not a closed loss.")
    if db.scalar(select(LossReview.id).where(LossReview.position_id == position_id)) is not None:
        raise Conflict(f"Position {position_id} has already been reviewed.")
    review = LossReview(position_id=position_id, reasons_json=json.dumps(_clean_reasons(reasons)),
                        mistakes=mistakes.strip(), lesson=lesson.strip(), algo_change=algo_change.strip(),
                        reviewed_on=date.today().isoformat())
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


def update_review(db: Session, review_id: int, reasons: list[str], mistakes: str, lesson: str,
                  algo_change: str) -> LossReview:
    review = db.get(LossReview, review_id)
    if review is None:
        raise NotFound(f"Review {review_id} not found.")
    review.reasons_json = json.dumps(_clean_reasons(reasons))
    review.mistakes, review.lesson, review.algo_change = mistakes.strip(), lesson.strip(), algo_change.strip()
    review.reviewed_on = date.today().isoformat()
    db.commit()
    db.refresh(review)
    return review


def summary(db: Session, profile_id: int) -> dict:
    profile_service.get_profile(db, profile_id)
    rows = _closed_losses(db, profile_id)
    reviews = list(db.scalars(select(LossReview).where(LossReview.position_id.in_([p.id for p in rows])))) if rows else []
    counts: dict[str, int] = {}
    for r in reviews:
        for tag in json.loads(r.reasons_json):
            counts[tag] = counts.get(tag, 0) + 1
    order = list(TAGS)
    by_tag = sorted(counts.items(), key=lambda kv: (-kv[1], order.index(kv[0]) if kv[0] in TAGS else len(order)))
    pcts = [p.pnl_pct for p in rows if p.pnl_pct is not None]
    return {
        "total_losses": len(rows), "reviewed": len(reviews),
        "by_tag": [{"key": k, "label": TAGS.get(k, k), "count": n} for k, n in by_tag],
        "avg_loss_pct": round(sum(pcts) / len(pcts), 2) if pcts else None,
    }
