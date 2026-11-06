"""Every SQLAlchemy table (see docs/DATA_MODEL.md). Importing this package registers them all on Base.metadata.
Import models from here: `from app.models import Profile, Position`.
"""
from app.models.backtest import Backtest, BacktestTrade
from app.models.brain import EvidencePackRow, MarketBriefRow
from app.models.meta import AppMeta
from app.models.pick_list import PickList
from app.models.position import Position, PositionEvent, PositionMark
from app.models.profile import Profile
from app.models.review import LossReview
from app.models.sources import (Announcement, BrainJob, Deal, InsiderTrade, MarketContextRow, NewsItem,
                                QuarterlyResult, Shareholding, SourcePull)
from app.models.suggestion import Suggestion, SuggestionRun

__all__ = [
    "Announcement",
    "AppMeta",
    "BrainJob",
    "Deal",
    "EvidencePackRow",
    "InsiderTrade",
    "MarketBriefRow",
    "MarketContextRow",
    "NewsItem",
    "QuarterlyResult",
    "Shareholding",
    "SourcePull",
    "Backtest",
    "BacktestTrade",
    "LossReview",
    "PickList",
    "Position",
    "PositionEvent",
    "PositionMark",
    "Profile",
    "Suggestion",
    "SuggestionRun",
]
