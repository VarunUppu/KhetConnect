# File: backend/app/deps.py
import uuid  # noqa: F401  (kept for later stages)

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.user import User
from app.services import auth_service
from app.services.auth_service import TokenError
from app.services.geo_service import lat_lng  # noqa: F401

# auto_error=False so a missing header gives 401 (FastAPI's default would be 403)
_bearer = HTTPBearer(auto_error=False)

__all__ = ["get_db", "get_current_user", "require_complete_profile"]


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status_code=401, detail=detail, headers={"WWW-Authenticate": "Bearer"})


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """JWT guard: add `user: User = Depends(get_current_user)` to any protected route."""
    if creds is None:
        raise _unauthorized("Not authenticated")
    try:
        user_id = auth_service.decode_access_token(creds.credentials)
    except TokenError:
        raise _unauthorized("Invalid or expired token") from None
    user = db.get(User, user_id)
    if user is None:
        raise _unauthorized("User no longer exists")
    return user


def require_complete_profile(user: User = Depends(get_current_user)) -> User:
    """For endpoints that need name + district + location (creating resources, bookings)."""
    if not (user.name and user.district and user.location is not None):
        raise HTTPException(403, "Complete your profile (name, district and location) first")
    return user