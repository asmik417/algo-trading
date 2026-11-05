"""The `loss_reviews` table: one post-mortem per closed losing position (tags, mistake, lesson, algo change).
Tag keys come from the fixed list in review_service.
"""
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.clock import utc_now_iso
from app.db.base import Base


class LossReview(Base):
    __tablename__ = "loss_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    position_id: Mapped[int] = mapped_column(ForeignKey("positions.id", ondelete="CASCADE"), nullable=False, unique=True)
    reasons_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    mistakes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    lesson: Mapped[str] = mapped_column(Text, nullable=False, default="")
    algo_change: Mapped[str] = mapped_column(Text, nullable=False, default="")
    reviewed_on: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso)

    position = relationship("Position", back_populates="review")
