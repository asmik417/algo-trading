"""The `backtests` and `backtest_trades` tables: one replay of a strategy over past dates, and its simulated trades.
Summary, breakdowns and caveats are stored as JSON once the backtest finishes (see docs/DATA_MODEL.md).
"""
from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.clock import utc_now_iso
from app.db.base import Base


class Backtest(Base):
    __tablename__ = "backtests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")  # queued, running, done, failed
    start_date: Mapped[str] = mapped_column(String(10), nullable=False)   # effective start once clamped
    end_date: Mapped[str] = mapped_column(String(10), nullable=False)
    frequency: Mapped[str] = mapped_column(String(10), nullable=False, default="weekly")
    entry_rule: Mapped[str] = mapped_column(String(16), nullable=False, default="next_close")
    fundamentals_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="point_in_time")
    cost_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.3)
    capital_per_trade: Mapped[float] = mapped_column(Float, nullable=False)
    params_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    scan_count: Mapped[int | None] = mapped_column(Integer)
    summary_json: Mapped[str | None] = mapped_column(Text)
    breakdowns_json: Mapped[str | None] = mapped_column(Text)
    caveats_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[str | None] = mapped_column(String(32))
    finished_at: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso)

    profile = relationship("Profile")
    trades = relationship("BacktestTrade", back_populates="backtest", cascade="all, delete-orphan", passive_deletes=True,
                          order_by="BacktestTrade.id")


class BacktestTrade(Base):
    __tablename__ = "backtest_trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    backtest_id: Mapped[int] = mapped_column(ForeignKey("backtests.id", ondelete="CASCADE"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    scan_date: Mapped[str] = mapped_column(String(10), nullable=False)
    entry_date: Mapped[str] = mapped_column(String(10), nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    invested: Mapped[float] = mapped_column(Float, nullable=False)
    stop_loss: Mapped[float] = mapped_column(Float, nullable=False)
    target: Mapped[float] = mapped_column(Float, nullable=False)
    planned_exit_date: Mapped[str] = mapped_column(String(10), nullable=False)
    signal: Mapped[str] = mapped_column(String(40), nullable=False)
    stage: Mapped[str] = mapped_column(String(40), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    market_cap_bucket: Mapped[str] = mapped_column(String(16), nullable=False)
    sector: Mapped[str | None] = mapped_column(String(80))
    exit_date: Mapped[str | None] = mapped_column(String(10))
    exit_price: Mapped[float | None] = mapped_column(Float)
    exit_reason: Mapped[str] = mapped_column(String(16), nullable=False)  # target_hit, stop_hit, horizon_closed, open
    pnl: Mapped[float] = mapped_column(Float, nullable=False)
    pnl_pct: Mapped[float] = mapped_column(Float, nullable=False)
    r_multiple: Mapped[float | None] = mapped_column(Float)
    days_held: Mapped[int] = mapped_column(Integer, nullable=False)
    mfe_pct: Mapped[float | None] = mapped_column(Float)
    mae_pct: Mapped[float | None] = mapped_column(Float)
    nifty_pct: Mapped[float | None] = mapped_column(Float)
    tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    backtest = relationship("Backtest", back_populates="trades")
