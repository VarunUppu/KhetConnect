# File: backend/app/routers/ratings.py
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.errors import not_implemented
from app.db import get_db
from app.deps import get_current_user
from app.models.user import User
from app.schemas.rating import RatingCreate, RatingListResponse, RatingOut

# No router prefix: these paths live under /bookings and /users.
router = APIRouter(tags=["ratings"])


@router.post("/bookings/{booking_id}/ratings", response_model=RatingOut, status_code=201)
def create_rating(
    booking_id: uuid.UUID,
    body: RatingCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    raise not_implemented("ratings.create")


@router.get("/users/{user_id}/ratings", response_model=RatingListResponse)
def list_user_ratings(
    user_id: uuid.UUID,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    raise not_implemented("ratings.list_for_user")