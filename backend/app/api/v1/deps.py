"""Shared FastAPI dependencies for v1 routers.
require_session guards every router except health and auth (wired in router.py).
"""
from fastapi import HTTPException, Request, status

from app.core.config import settings
from app.services import auth_service

NOT_AUTHENTICATED = "Not authenticated"


def require_session(request: Request) -> str:
    """The logged-in username, or 401 {"detail": "Not authenticated"}."""
    username = auth_service.read_token(request.cookies.get(settings.SESSION_COOKIE))
    if username is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=NOT_AUTHENTICATED)
    return username
