"""Profiles ("accounts"): create, edit, delete, activate, and the Account-page param spec.
Every params change is validated by ScreenParams.validate(); exactly one profile is kept active.
"""
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.clock import utc_now_iso
from app.core.logging import get_logger
from app.engine.params import CAP_BUCKETS, DEFAULTS, HORIZONS, PARAM_SPEC, ScreenParams
from app.models import Profile
from app.services.errors import BadInput, Conflict, NotFound

log = get_logger(__name__)

DEFAULT_PROFILE_NAME = "Default – Balanced"
DEFAULT_PROFILE_OWNER = "Roshan"


# --- shaping -----------------------------------------------------------------

def params_of(profile: Profile) -> ScreenParams:
    return ScreenParams.from_json(profile.params_json)


def to_schema(profile: Profile) -> dict:
    params = params_of(profile)
    return {
        "id": profile.id,
        "name": profile.name,
        "owner": profile.owner,
        "is_active": profile.is_active,
        "params": params.to_dict(),
        "params_summary": params.summary(),
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
    }


def param_spec() -> dict:
    return {
        "defaults": dict(DEFAULTS),
        "horizons": list(HORIZONS),
        "cap_buckets": list(CAP_BUCKETS),
        "sections": PARAM_SPEC,
    }


# --- validation --------------------------------------------------------------

def _clean_text(value: str | None, field: str) -> str:
    text = (value or "").strip()
    if not text:
        raise BadInput(f"{field} must not be empty.")
    return text


def _build_params(base: dict, changes: dict | None) -> ScreenParams:
    changes = changes or {}
    unknown = sorted(set(changes) - set(DEFAULTS))
    problems = [f"Unknown parameter: {k}." for k in unknown]
    params = ScreenParams.from_dict({**base, **changes})
    problems += params.validate()
    if problems:
        raise BadInput(" ".join(problems))
    return params


def _ensure_unique_name(db: Session, name: str, exclude_id: int | None = None) -> None:
    q = select(Profile.id).where(Profile.name == name)
    if exclude_id is not None:
        q = q.where(Profile.id != exclude_id)
    if db.scalar(q) is not None:
        raise Conflict(f"A profile named '{name}' already exists.")


# --- queries -----------------------------------------------------------------

def list_profiles(db: Session) -> list[Profile]:
    return list(db.scalars(select(Profile).order_by(Profile.id)))


def get_profile(db: Session, profile_id: int) -> Profile:
    profile = db.get(Profile, profile_id)
    if profile is None:
        raise NotFound(f"Profile {profile_id} not found.")
    return profile


def get_active(db: Session) -> Profile:
    profile = db.scalar(select(Profile).where(Profile.is_active.is_(True)).order_by(Profile.id))
    if profile is None:
        raise NotFound("No active profile.")
    return profile


# --- commands ----------------------------------------------------------------

def create_profile(db: Session, name: str, owner: str | None, params: dict | None = None,
                   default_owner: str | None = None) -> Profile:
    """`owner` is hidden in the UI now: when missing or blank it defaults to the logged-in username."""
    name = _clean_text(name, "Name")
    owner = _clean_text(owner if (owner or "").strip() else default_owner, "Owner")
    validated = _build_params(DEFAULTS, params)
    _ensure_unique_name(db, name)
    is_first = db.scalar(select(Profile.id).limit(1)) is None
    profile = Profile(name=name, owner=owner, params_json=validated.to_json(), is_active=is_first)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    log.info("Created profile %s (%s)", profile.id, profile.name)
    return profile


def update_profile(db: Session, profile_id: int, name: str | None = None, owner: str | None = None,
                   params: dict | None = None) -> Profile:
    profile = get_profile(db, profile_id)
    if name is not None:
        name = _clean_text(name, "Name")
        _ensure_unique_name(db, name, exclude_id=profile.id)
        profile.name = name
    if owner is not None:
        profile.owner = _clean_text(owner, "Owner")
    if params is not None:
        # Partial params are merged onto the stored ones, so the form can send only what changed.
        profile.params_json = _build_params(params_of(profile).to_dict(), params).to_json()
    profile.updated_at = utc_now_iso()
    db.commit()
    db.refresh(profile)
    return profile


def delete_profile(db: Session, profile_id: int) -> None:
    profile = get_profile(db, profile_id)
    was_active = profile.is_active
    db.delete(profile)
    db.flush()
    if was_active:  # keep exactly one active profile while any exist
        successor = db.scalar(select(Profile).order_by(Profile.id).limit(1))
        if successor is not None:
            successor.is_active = True
    db.commit()
    log.info("Deleted profile %s", profile_id)


def activate_profile(db: Session, profile_id: int) -> Profile:
    profile = get_profile(db, profile_id)
    db.execute(update(Profile).where(Profile.id != profile.id).values(is_active=False))
    profile.is_active = True
    db.commit()
    db.refresh(profile)
    return profile


def seed_default_profile(db: Session) -> Profile | None:
    """On first startup create one active default profile; no-op when any profile exists."""
    if db.scalar(select(Profile.id).limit(1)) is not None:
        return None
    profile = Profile(name=DEFAULT_PROFILE_NAME, owner=DEFAULT_PROFILE_OWNER,
                      params_json=ScreenParams.from_dict({}).to_json(), is_active=True)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    log.info("Seeded default profile '%s'", profile.name)
    return profile
