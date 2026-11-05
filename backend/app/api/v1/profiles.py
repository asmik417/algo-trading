"""Profile endpoints: CRUD, activate, active profile and the Account-page param spec.
Thin router: all rules live in services/profile_service.py.
"""
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.v1.deps import require_session
from app.db.session import get_db
from app.schemas.profile import ParamSpec, Profile, CreateProfileBody, UpdateProfileBody
from app.services import profile_service

router = APIRouter(prefix="/profiles", tags=["profiles"])


# Static paths first so "param-spec" / "active" are never parsed as an {id}.
@router.get("/param-spec", response_model=ParamSpec, response_model_exclude_none=True)
def get_param_spec():
    return profile_service.param_spec()


@router.get("/active", response_model=Profile)
def get_active_profile(db: Session = Depends(get_db)):
    return profile_service.to_schema(profile_service.get_active(db))


@router.get("", response_model=list[Profile])
def list_profiles(db: Session = Depends(get_db)):
    return [profile_service.to_schema(p) for p in profile_service.list_profiles(db)]


@router.post("", response_model=Profile, status_code=status.HTTP_201_CREATED)
def create_profile(body: CreateProfileBody, db: Session = Depends(get_db), username: str = Depends(require_session)):
    p = profile_service.create_profile(db, body.name, body.owner, body.params, default_owner=username)
    return profile_service.to_schema(p)


@router.get("/{profile_id}", response_model=Profile)
def get_profile(profile_id: int, db: Session = Depends(get_db)):
    return profile_service.to_schema(profile_service.get_profile(db, profile_id))


@router.put("/{profile_id}", response_model=Profile)
def update_profile(profile_id: int, body: UpdateProfileBody, db: Session = Depends(get_db)):
    p = profile_service.update_profile(db, profile_id, body.name, body.owner, body.params)
    return profile_service.to_schema(p)


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(profile_id: int, db: Session = Depends(get_db)):
    profile_service.delete_profile(db, profile_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{profile_id}/activate", response_model=Profile)
def activate_profile(profile_id: int, db: Session = Depends(get_db)):
    return profile_service.to_schema(profile_service.activate_profile(db, profile_id))
