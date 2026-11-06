"""Tables the brain builds from the source tables (docs/DATA_MODEL.md -> evidence_packs, market_briefs).
One evidence pack per (symbol, day) and one market brief per day; a rebuild replaces the row for that key.
"""
from sqlalchemy import Boolean, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now_iso
from app.db.base import Base


class EvidencePackRow(Base):
    __tablename__ = "evidence_packs"
    __table_args__ = (UniqueConstraint("symbol", "day", name="uq_evidence_pack_symbol_day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    day: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    pack_json: Mapped[str] = mapped_column(Text, nullable=False)          # EvidencePack
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso)


class MarketBriefRow(Base):
    __tablename__ = "market_briefs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    day: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    brief_json: Mapped[str] = mapped_column(Text, nullable=False)         # MarketBrief
    audited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # model text passed the audit
    audit_notes_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    model: Mapped[str | None] = mapped_column(String(64))                 # None: deterministic fallback text
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso)
