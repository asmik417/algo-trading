"""Auth endpoints: log in (sets the signed session cookie), who am I, log out (clears it).
Single user; credentials live in backend/.env. Rules in services/auth_service.py.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.api.v1.deps import require_session
from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.auth import LoginBody, Me
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])
log = get_logger(__name__)


def _cookie_args() -> dict:
    return {"key": settings.SESSION_COOKIE, "httponly": True, "samesite": "lax", "secure": settings.COOKIE_SECURE,
            "path": "/"}


@router.post("/login", response_model=Me)
def login(body: LoginBody, request: Request, response: Response):
    # The direct peer address; X-Forwarded-For is not trusted (it can be forged by the client).
    ip = request.client.host if request.client else "unknown"
    if auth_service.is_blocked(ip):  # checked before the password, so a blocked client cannot keep guessing
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many attempts, try again later")
    if not auth_service.check_credentials(body.username, body.password):
        auth_service.record_failure(ip)
        log.warning("Failed login from %s", ip)  # never log the submitted username or password
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong username or password.")
    auth_service.record_success(ip)
    response.set_cookie(value=auth_service.make_token(settings.APP_USERNAME), max_age=settings.SESSION_MAX_AGE,
                        **_cookie_args())
    return {"username": settings.APP_USERNAME}


@router.get("/me", response_model=Me)
def me(username: str = Depends(require_session)):
    return {"username": username}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout():
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(**_cookie_args())
    return response
