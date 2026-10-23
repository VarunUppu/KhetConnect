# File: backend/app/schemas/rating.py
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.user import UserPublic


class RatingCreate(BaseModel):
    score: int = Field(ge=1, le=5)
    comment: str | None = Field(None, max_length=500)


class RatingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    booking_id: uuid.UUID
    rated_by: UserPublic
    rated_user_id: uuid.UUID
    score: int
    comment: str | None
    created_at: datetime


class RatingListResponse(BaseModel):
    items: list[RatingOut]
    total: int
    limit: int
    offset: int