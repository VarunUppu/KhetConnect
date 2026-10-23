# File: backend/app/schemas/user.py
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# A user is a farmer, a provider, or both ("both" is the multi-role case).
UserRole = Literal["farmer", "provider", "both"]
LanguageCode = Literal["hi", "en", "te", "ta", "kn", "mr", "bn", "gu", "pa", "ml", "or"]


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str | None = None
    role: UserRole
    village: str | None = None
    district: str | None = None
    trust_score: float = 0
    rating_count: int = 0


class UserPrivate(UserPublic):
    phone_number: str
    lat: float | None = None
    lng: float | None = None
    language_pref: LanguageCode
    created_at: datetime
    profile_complete: bool


class UserUpdate(BaseModel):
    """Partial update. Omitted or null fields are left unchanged."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100)
    role: UserRole | None = None
    village: str | None = Field(default=None, min_length=1, max_length=100)
    district: str | None = Field(default=None, min_length=1, max_length=100)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    language_pref: LanguageCode | None = None

    @field_validator("name", "village", "district", mode="before")
    @classmethod
    def _strip(cls, v):
        return v.strip() if isinstance(v, str) else v

    @model_validator(mode="after")
    def _lat_lng_together(self) -> "UserUpdate":
        if (self.lat is None) != (self.lng is None):
            raise ValueError("lat and lng must be sent together")
        return self