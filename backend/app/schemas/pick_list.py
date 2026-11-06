"""Request and response shapes for pick lists (named, saved symbol lists for My Picks).
Mirrors the Pick lists section of docs/API_CONTRACT.md.
"""
from app.schemas.common import ApiModel


class PickList(ApiModel):
    id: int
    name: str
    symbols: list[str]
    created_at: str
    updated_at: str


class CreatePickListBody(ApiModel):
    name: str
    symbols: list[str]


class UpdatePickListBody(ApiModel):
    name: str | None = None
    symbols: list[str] | None = None
