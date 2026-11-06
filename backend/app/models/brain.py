"""Tables the brain builds (docs/DATA_MODEL.md): evidence packs, market briefs, analyst views, the verdict log and its
20/40/60-session marks. Packs and briefs are replaced on rebuild; views, log rows and marks are written once.
"""
from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
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


class AnalystViewRow(Base):
    """One analyst view per (symbol, day, profile); `view_json` is the AnalystView without id/created_at."""
    __tablename__ = "analyst_views"
    __table_args__ = (UniqueConstraint("symbol", "day", "profile_id", name="uq_analyst_view"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    day: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    view_json: Mapped[str] = mapped_column(Text, nullable=False)
    audited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")   # exactly what the model was given
    usage_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")      # tokens and searches, all calls
    cost_usd: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso)


class VerdictLogRow(Base):
    """Every rules verdict and analyst view, once per (symbol, day, source, profile), with that day's close."""
    __tablename__ = "verdict_log"
    __table_args__ = (UniqueConstraint("symbol", "day", "source", "profile_id", name="uq_verdict_log"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    day: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(8), nullable=False)          # rules | analyst
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(8), nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)       # up | down | sideways
    level: Mapped[float | None] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    signal: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso)


class VerdictMarkRow(Base):
    __tablename__ = "verdict_marks"

    verdict_id: Mapped[int] = mapped_column(ForeignKey("verdict_log.id", ondelete="CASCADE"), primary_key=True)
    sessions: Mapped[int] = mapped_column(Integer, primary_key=True)        # 20 | 40 | 60
    mark_date: Mapped[str] = mapped_column(String(10), nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    change_pct: Mapped[float] = mapped_column(Float, nullable=False)
    right: Mapped[bool] = mapped_column(Boolean, nullable=False)
