"""The `app_meta` key/value table: last_daily_update, last_trading_day, panel_built_for, daily job summary.
Small facts the app needs to remember between restarts.
"""
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AppMeta(Base):
    __tablename__ = "app_meta"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text)
