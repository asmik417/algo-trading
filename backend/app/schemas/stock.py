"""Response shapes for the Explore screen: the full NSE universe table and a single stock's detail.
Mirrors the Stocks section of docs/API_CONTRACT.md.
"""
from app.schemas.common import ApiModel
from app.schemas.suggestion import ChartData, Indicators


class StockRow(ApiModel):
    symbol: str
    close: float
    change_1d_pct: float | None
    change_1w_pct: float | None
    change_1m_pct: float | None
    change_3m_pct: float | None
    dist_from_52w_high_pct: float | None
    volume_ratio_20d: float | None
    avg_turnover_lacs: float | None


class StocksResponse(ApiModel):
    trading_day: str
    total: int
    items: list[StockRow]


class StockDetail(ApiModel):
    symbol: str
    trading_day: str
    close: float
    metrics: StockRow
    indicators: Indicators
    chart: ChartData
