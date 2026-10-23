# File: backend/app/services/auth_service.py
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import User


class TokenError(Exception):
    """The access token is missing a required claim, malformed, expired or badly signed."""


def create_access_token(user_id: uuid.UUID) -> tuple[str, int]:
    """Returns (jwt, expires_in_seconds)."""
    now = datetime.now(timezone.utc)
    expires_in = settings.ACCESS_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    payload = {"sub": str(user_id), "iat": now, "exp": now + timedelta(seconds=expires_in)}
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return token, expires_in


def decode_access_token(token: str) -> uuid.UUID:
    """Returns the user id from a valid token; raises TokenError otherwise."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],  # pinned: rejects alg=none and algorithm swaps
            options={"require": ["exp", "iat", "sub"]},
            leeway=10,
        )
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc
    try:
        return uuid.UUID(str(payload["sub"]))
    except (ValueError, TypeError) as exc:
        raise TokenError("Invalid subject claim") from exc


def get_or_create_user(db: Session, phone_number: str) -> tuple[User, bool]:
    """Returns (user, is_new_user)."""
    user = db.execute(select(User).where(User.phone_number == phone_number)).scalar_one_or_none()
    if user is not None:
        return user, False

    user = User(phone_number=phone_number)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # two simultaneous first logins: the other request won the race
        db.rollback()
        user = db.execute(select(User).where(User.phone_number == phone_number)).scalar_one()
        return user, False
    db.refresh(user)
    return user, True