# File: backend/app/routers/users.py
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.user import UserPrivate, UserPublic, UserUpdate
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserPrivate)
def get_me(user: User = Depends(get_current_user)):
    return user_service.to_private(user)


@router.patch("/me", response_model=UserPrivate)
@router.put("/me", response_model=UserPrivate)
def update_me(
    body: UserUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """PUT and PATCH behave identically: only the fields you send are changed."""
    data = body.model_dump(exclude_none=True)
    user = user_service.update_profile(db, user, data)
    return user_service.to_private(user)


@router.get("/{user_id}", response_model=UserPublic)
def get_user(
    user_id: uuid.UUID,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(404, "User not found")
    return user_service.to_public(target)


@router.get("/{user_id}/ratings")
def get_user_ratings(user_id: uuid.UUID, _: User = Depends(get_current_user)):
    # Implemented in Stage 3 (Bookings & Ratings)
    raise HTTPException(501, "Not implemented yet")