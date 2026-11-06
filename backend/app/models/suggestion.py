"""The `suggestion_runs` and `suggestions` tables: algo runs (full market or a watchlist) and the stocks they scored.
Each suggestion freezes its plan and score payload; source is "run", "explore" (ad-hoc, no run) or "watchlist".
"""
from sqlalchemy import Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.clock import utc_now_iso
from app.db.base import Base


class SuggestionRun(Base):
    __tablename__ = "suggestion_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    trading_day: Mapped[str | None] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")  # queued, running, done, failed
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="full", server_default="full")  # full | watchlist
    symbols_json: Mapped[str | None] = mapped_column(Text)       # watchlist: requested symbols, in order; null for full
    item_errors_json: Mapped[str | None] = mapped_column(Text)   # watchlist: {symbol: why it could not be analysed}
    list_id: Mapped[int | None] = mapped_column(ForeignKey("pick_lists.id", ondelete="SET NULL"))  # watchlist from a list
    universe_size: Mapped[int | None] = mapped_column(Integer)
    scored_size: Mapped[int | None] = mapped_column(Integer)
    passed_size: Mapped[int | None] = mapped_column(Integer)
    params_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[str | None] = mapped_column(String(32))
    finished_at: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso)

    profile = relationship("Profile", back_populates="runs")
    pick_list = relationship("PickList")  # read-only lookup for list_name; the DB nulls list_id on list delete
    suggestions = relationship("Suggestion", back_populates="run", cascade="all, delete-orphan", passive_deletes=True)


class Suggestion(Base):
    __tablename__ = "suggestions"
    # NULL run_ids never collide, so ad-hoc Explore rows may repeat per symbol.
    __table_args__ = (UniqueConstraint("run_id", "symbol", name="uq_suggestion_run_symbol"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("suggestion_runs.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(String(8), nullable=False, default="run", index=True)  # run | explore
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    trading_day: Mapped[str] = mapped_column(String(10), nullable=False)
    rank: Mapped[int | None] = mapped_column(Integer)  # None for explore rows (not ranked in a run)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    stage: Mapped[str] = mapped_column(String(40), nullable=False)
    signal: Mapped[str] = mapped_column(String(40), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    entry_aggressive: Mapped[float] = mapped_column(Float, nullable=False)
    entry_optimal: Mapped[float] = mapped_column(Float, nullable=False)
    entry_conservative: Mapped[float] = mapped_column(Float, nullable=False)
    stop_loss: Mapped[float] = mapped_column(Float, nullable=False)
    target: Mapped[float] = mapped_column(Float, nullable=False)
    risk_reward: Mapped[float] = mapped_column(Float, nullable=False)
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    planned_exit_date: Mapped[str] = mapped_column(String(10), nullable=False)
    timing_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    exit_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    positives_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    risks_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    narration_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso)

    run = relationship("SuggestionRun", back_populates="suggestions")
