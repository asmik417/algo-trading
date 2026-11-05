"""The `positions`, `position_events` and `position_marks` tables: paper trades, their audit trail and daily valuations.
Derived fields (cash_left, current_value, days_held, days_to_exit, needs_review) are computed in tracker_service.
"""
from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.clock import utc_now_iso
from app.db.base import Base


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    suggestion_id: Mapped[int | None] = mapped_column(ForeignKey("suggestions.id", ondelete="SET NULL"), index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    opened_on: Mapped[str] = mapped_column(String(10), nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    invested: Mapped[float] = mapped_column(Float, nullable=False)
    capital: Mapped[float] = mapped_column(Float, nullable=False)
    target: Mapped[float | None] = mapped_column(Float)
    stop_loss: Mapped[float | None] = mapped_column(Float)
    original_exit_date: Mapped[str] = mapped_column(String(10), nullable=False)
    planned_exit_date: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="open", index=True)  # open, due, closed
    last_mark_date: Mapped[str | None] = mapped_column(String(10))
    last_close: Mapped[float | None] = mapped_column(Float)
    closed_on: Mapped[str | None] = mapped_column(String(10))
    exit_price: Mapped[float | None] = mapped_column(Float)
    pnl: Mapped[float | None] = mapped_column(Float)
    pnl_pct: Mapped[float | None] = mapped_column(Float)
    close_reason: Mapped[str | None] = mapped_column(String(20))  # target_hit, stop_hit, horizon_closed, manual
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso)

    profile = relationship("Profile", back_populates="positions")
    suggestion = relationship("Suggestion")
    events = relationship("PositionEvent", back_populates="position", cascade="all, delete-orphan",
                          passive_deletes=True, order_by="PositionEvent.id")
    marks = relationship("PositionMark", back_populates="position", cascade="all, delete-orphan",
                         passive_deletes=True, order_by="PositionMark.mark_date")
    review = relationship("LossReview", back_populates="position", uselist=False, cascade="all, delete-orphan",
                          passive_deletes=True)


class PositionEvent(Base):
    __tablename__ = "position_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    position_id: Mapped[int] = mapped_column(ForeignKey("positions.id", ondelete="CASCADE"), nullable=False, index=True)
    event_date: Mapped[str] = mapped_column(String(10), nullable=False)
    event_type: Mapped[str] = mapped_column(String(10), nullable=False)  # open, extend, shorten, due, close, note
    old_exit_date: Mapped[str | None] = mapped_column(String(10))
    new_exit_date: Mapped[str | None] = mapped_column(String(10))
    reason: Mapped[str | None] = mapped_column(Text)
    price: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso)

    position = relationship("Position", back_populates="events")


class PositionMark(Base):
    __tablename__ = "position_marks"

    position_id: Mapped[int] = mapped_column(ForeignKey("positions.id", ondelete="CASCADE"), primary_key=True)
    mark_date: Mapped[str] = mapped_column(String(10), primary_key=True)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    pnl: Mapped[float] = mapped_column(Float, nullable=False)
    pnl_pct: Mapped[float] = mapped_column(Float, nullable=False)

    position = relationship("Position", back_populates="marks")
