"""Response shape for GET /health.
Mirrors the Health section of docs/API_CONTRACT.md.
"""
from app.schemas.common import ApiModel


class Health(ApiModel):
    status: str
    trading_day: str | None
    db: str
