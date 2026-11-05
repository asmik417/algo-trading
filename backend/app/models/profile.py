"""The `profiles` table: a named set of screening parameters that acts as the user's "account".
Exactly one profile is active at a time; profile_service enforces that.
"""
from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.clock import utc_now_iso
from app.db.base import Base


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    owner: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    params_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso, onupdate=utc_now_iso)

    runs = relationship("SuggestionRun", back_populates="profile", cascade="all, delete-orphan", passive_deletes=True)
    positions = relationship("Position", back_populates="profile", cascade="all, delete-orphan", passive_deletes=True)
