"""Response shapes for the brain: evidence packs and market briefs.
Mirrors "The brain" section of docs/API_CONTRACT.md (EvidencePack, MarketBrief and their parts).
"""
from typing import Literal

from app.schemas.common import ApiModel
from app.schemas.suggestion import Plan, Verdict

Regime = Literal["risk_on", "neutral", "risk_off"]


class QuarterRow(ApiModel):
    period: str
    filed_on: str | None
    revenue: float | None
    ebitda: float | None
    net_profit: float | None
    eps: float | None
    margin_pct: float | None


class Ownership(ApiModel):
    as_of: str | None
    promoter_pct: float | None
    promoter_change_pct: float | None
    fii_pct: float | None
    dii_pct: float | None
    public_pct: float | None
    pledge_pct: float | None


class DealRow(ApiModel):
    date: str
    kind: Literal["bulk", "block", "insider_buy", "insider_sell"]
    party: str
    qty: float
    price: float | None


class EventRow(ApiModel):
    date: str
    kind: str
    title: str


class Headline(ApiModel):
    date: str
    title: str
    source: str
    url: str


class MarketContext(ApiModel):
    day: str
    nifty_close: float | None
    nifty_vs_ema50_pct: float | None
    nifty_1w_pct: float | None
    vix: float | None
    advance_decline: float | None
    fii_net_cr: float | None
    dii_net_cr: float | None
    sector_index: str | None
    sector_1w_pct: float | None
    sp500_1d_pct: float | None
    crude_1w_pct: float | None
    usdinr_1w_pct: float | None


class EvidencePrice(ApiModel):
    close: float
    change_1w_pct: float | None
    change_1m_pct: float | None
    change_3m_pct: float | None
    vs_nifty_1m_pct: float | None
    vs_sector_1m_pct: float | None
    dist_52w_high_pct: float | None
    volume_ratio: float | None
    delivery_pct_now: float | None
    delivery_pct_prev: float | None
    ema_trend: str | None
    rsi: float | None


class EvidencePack(ApiModel):
    symbol: str
    day: str
    price: EvidencePrice
    quarters: list[QuarterRow]
    ownership: Ownership | None
    deals: list[DealRow]
    events: list[EventRow]
    headlines: list[Headline]
    market: MarketContext
    rules_verdict: Verdict | None
    plan: Plan | None
    unavailable: list[str]


class IndexMove(ApiModel):
    index: str
    change_1w_pct: float


class MarketBrief(ApiModel):
    day: str
    regime: Regime
    context: MarketContext
    leaders: list[IndexMove]
    laggards: list[IndexMove]
    facts: list[str]
    paragraph: str
    stance: str
    created_at: str
