"""The `pick_lists` table: named, saved lists of symbols for My Picks (e.g. "Manager holdings").
Independent of strategies; watchlist runs may point at one (suggestion_runs.list_id, set null on delete).
"""
from sqlalchemy import Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now_iso
from app.db.base import Base


class PickList(Base):
    __tablename__ = "pick_lists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(60), nullable=False)   # stored trimmed
    symbols_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso)


# Names are unique ignoring case (an index on lower(name)); the service returns 409 before the DB would refuse.
Index("uq_pick_lists_name_ci", func.lower(PickList.name), unique=True)
