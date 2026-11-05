"""Request and response shapes for single-user login.
Mirrors the Auth section of docs/API_CONTRACT.md.
"""
from app.schemas.common import ApiModel


class LoginBody(ApiModel):
    username: str
    password: str


class Me(ApiModel):
    username: str
