# File: backend/app/services/user_service.py
from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.user import UserPrivate, UserPublic
from app.services.geo_service import lat_lng, make_point


def to_public(user: User) -> UserPublic:
    return UserPublic.model_validate(user)


def to_private(user: User) -> UserPrivate:
    lat, lng = lat_lng(user.location)
    return UserPrivate(
        **to_public(user).model_dump(),
        phone_number=user.phone_number,
        lat=lat,
        lng=lng,
        language_pref=user.language_pref,
        created_at=user.created_at,
        profile_complete=bool(user.name and user.district and user.location is not None),
    )


def update_profile(db: Session, user: User, data: dict) -> User:
    """`data` holds only the fields to change (already validated, None values removed)."""
    data = dict(data)
    lat = data.pop("lat", None)
    lng = data.pop("lng", None)
    for field, value in data.items():
        setattr(user, field, value)
    if lat is not None and lng is not None:
        user.location = make_point(lat, lng)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user