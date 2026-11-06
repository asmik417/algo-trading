"""Pick lists: create, rename, replace symbols, delete, list. Names are unique ignoring case and spaces at the ends.
Symbols get the same cleaning as watchlist runs (upper-cased, de-duplicated, order kept, 1-50).
"""
import json

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.clock import utc_now_iso
from app.models import PickList
from app.services.errors import BadInput, Conflict, NotFound
from app.services.suggestion_service import clean_watchlist

MAX_NAME = 60


def to_schema(pl: PickList) -> dict:
    return {"id": pl.id, "name": pl.name, "symbols": json.loads(pl.symbols_json), "created_at": pl.created_at,
            "updated_at": pl.updated_at}


def _clean_name(name: str | None) -> str:
    name = (name or "").strip()
    if not name:
        raise BadInput("List name must not be empty.")
    if len(name) > MAX_NAME:
        raise BadInput(f"List name must be at most {MAX_NAME} characters.")
    return name


def _ensure_unique(db: Session, name: str, exclude_id: int | None = None) -> None:
    q = select(PickList.id).where(func.lower(PickList.name) == name.lower())
    if exclude_id is not None:
        q = q.where(PickList.id != exclude_id)
    if db.scalar(q) is not None:
        raise Conflict(f"A list named '{name}' already exists.")


def _commit(db: Session, name: str) -> None:
    try:
        db.commit()
    except IntegrityError:  # two requests raced past _ensure_unique; the lower(name) index still refuses
        db.rollback()
        raise Conflict(f"A list named '{name}' already exists.") from None


def get(db: Session, list_id: int) -> PickList:
    pl = db.get(PickList, list_id)
    if pl is None:
        raise NotFound(f"Pick list {list_id} not found.")
    return pl


def list_all(db: Session) -> list[PickList]:
    return list(db.scalars(select(PickList).order_by(PickList.updated_at.desc(), PickList.id.desc())))


def create(db: Session, name: str, symbols: list[str]) -> PickList:
    name, cleaned = _clean_name(name), clean_watchlist(symbols)
    _ensure_unique(db, name)
    pl = PickList(name=name, symbols_json=json.dumps(cleaned))
    db.add(pl)
    _commit(db, name)
    db.refresh(pl)
    return pl


def update(db: Session, list_id: int, name: str | None = None, symbols: list[str] | None = None) -> PickList:
    pl = get(db, list_id)
    if name is not None:
        name = _clean_name(name)
        _ensure_unique(db, name, exclude_id=pl.id)
        pl.name = name
    if symbols is not None:
        pl.symbols_json = json.dumps(clean_watchlist(symbols))
    pl.updated_at = utc_now_iso()
    _commit(db, pl.name)
    db.refresh(pl)
    return pl


def delete(db: Session, list_id: int) -> None:
    """Past runs of the list are kept; the database sets their list_id to null."""
    db.delete(get(db, list_id))
    db.commit()
