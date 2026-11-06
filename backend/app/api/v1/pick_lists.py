"""Pick list endpoints: list, create, update (rename and/or replace symbols), delete.
Thin router: rules live in services/pick_list_service.py.
"""
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.pick_list import CreatePickListBody, PickList, UpdatePickListBody
from app.services import pick_list_service

router = APIRouter(prefix="/pick-lists", tags=["pick-lists"])


@router.get("", response_model=list[PickList])
def list_pick_lists(db: Session = Depends(get_db)):
    return [pick_list_service.to_schema(pl) for pl in pick_list_service.list_all(db)]


@router.post("", response_model=PickList, status_code=status.HTTP_201_CREATED)
def create_pick_list(body: CreatePickListBody, db: Session = Depends(get_db)):
    return pick_list_service.to_schema(pick_list_service.create(db, body.name, body.symbols))


@router.put("/{list_id}", response_model=PickList)
def update_pick_list(list_id: int, body: UpdatePickListBody, db: Session = Depends(get_db)):
    return pick_list_service.to_schema(pick_list_service.update(db, list_id, body.name, body.symbols))


@router.delete("/{list_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pick_list(list_id: int, db: Session = Depends(get_db)):
    pick_list_service.delete(db, list_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
