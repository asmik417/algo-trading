"""Tables filled by the brain's source pullers (docs/DATA_MODEL.md -> source_pulls and the per-source tables).
Insert-only: every row has a unique `uid` built from the source's own identifiers, and a re-pull adds only new uids.
"""
from sqlalchemy import Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now_iso
from app.db.base import Base


class SourcePull(Base):
    __tablename__ = "source_pulls"
    __table_args__ = (UniqueConstraint("source", "day", name="uq_source_pull_day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    day: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(8), nullable=False)        # ok | empty | failed
    records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    inserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    pulled_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso)


class BrainJob(Base):
    """One nightly-brain run (POST /jobs/nightly-brain returns its id)."""
    __tablename__ = "brain_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    day: Mapped[str | None] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(8), nullable=False, default="queued")  # queued, running, done, failed
    summary_json: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[str | None] = mapped_column(String(32))
    finished_at: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso)


class _SourceRow:
    """Columns every source table shares."""
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uid: Mapped[str] = mapped_column(String(400), nullable=False, unique=True)
    pulled_day: Mapped[str] = mapped_column(String(10), nullable=False)      # the day whose pull inserted it
    data_json: Mapped[str] = mapped_column(Text, nullable=False)             # the record as normalised by the puller
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso)


class Announcement(_SourceRow, Base):
    __tablename__ = "announcements"
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    at: Mapped[str | None] = mapped_column(String(32))
    kind: Mapped[str] = mapped_column(String(160), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str | None] = mapped_column(Text)


class Deal(_SourceRow, Base):
    __tablename__ = "deals"
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(8), nullable=False)            # bulk | block
    side: Mapped[str | None] = mapped_column(String(8))
    party: Mapped[str] = mapped_column(String(200), nullable=False)
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float | None] = mapped_column(Float)


class InsiderTrade(_SourceRow, Base):
    __tablename__ = "insider_trades"
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    side: Mapped[str | None] = mapped_column(String(8))                      # buy | sell
    party: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str | None] = mapped_column(String(120))
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    value: Mapped[float | None] = mapped_column(Float)
    price: Mapped[float | None] = mapped_column(Float)


class Shareholding(_SourceRow, Base):
    __tablename__ = "shareholding"
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(8), nullable=False)            # pattern | pledge
    filed_on: Mapped[str] = mapped_column(String(10), nullable=False)
    as_of: Mapped[str | None] = mapped_column(String(10))
    promoter_pct: Mapped[float | None] = mapped_column(Float)
    public_pct: Mapped[float | None] = mapped_column(Float)
    pledge_pct: Mapped[float | None] = mapped_column(Float)


class MarketContextRow(_SourceRow, Base):
    __tablename__ = "market_context"
    day: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    metric: Mapped[str] = mapped_column(String(80), nullable=False)          # e.g. vix, fii_net_cr, global:sp500
    value: Mapped[float | None] = mapped_column(Float)


class NewsItem(_SourceRow, Base):
    __tablename__ = "news_items"
    symbol: Mapped[str | None] = mapped_column(String(32), index=True)       # null for market-wide feeds
    date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)


class QuarterlyResult(_SourceRow, Base):
    __tablename__ = "quarterly_results"
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    period_end: Mapped[str] = mapped_column(String(10), nullable=False)
    filed_on: Mapped[str] = mapped_column(String(10), nullable=False, index=True)  # point-in-time key for backtests
    nature: Mapped[str | None] = mapped_column(String(20))                  # Consolidated | Standalone
    revenue: Mapped[float | None] = mapped_column(Float)
    ebitda: Mapped[float | None] = mapped_column(Float)
    net_profit: Mapped[float | None] = mapped_column(Float)
    eps: Mapped[float | None] = mapped_column(Float)
    margin_pct: Mapped[float | None] = mapped_column(Float)
