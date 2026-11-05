"""Request and response shapes for profiles (the "accounts") and the Account-page param spec.
Mirrors the Profiles section of docs/API_CONTRACT.md.
"""
from typing import Any, Literal

from app.schemas.common import ApiModel, Params

FieldType = Literal["number", "int", "bool", "select", "multiselect"]


class ParamField(ApiModel):
    key: str
    label: str
    type: FieldType
    min: float | None = None
    max: float | None = None
    step: float | None = None
    options: list[str] | None = None
    help: str | None = None


class ParamSection(ApiModel):
    section: str
    help: str | None = None
    fields: list[ParamField]


class ParamSpec(ApiModel):
    defaults: dict[str, Any]
    horizons: list[str]
    cap_buckets: list[str]
    sections: list[ParamSection]


class Profile(ApiModel):
    id: int
    name: str
    owner: str
    is_active: bool
    params: Params
    params_summary: str
    created_at: str
    updated_at: str


class CreateProfileBody(ApiModel):
    name: str
    owner: str | None = None  # defaults to the logged-in username (contract: owner?: string)
    params: dict[str, Any] | None = None


class UpdateProfileBody(ApiModel):
    name: str | None = None
    owner: str | None = None
    params: dict[str, Any] | None = None
