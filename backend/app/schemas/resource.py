# File: backend/app/schemas/resource.py
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.enums import ResourceType
from app.schemas.user import UserPublic


class ResourceCreate(BaseModel):
    type: ResourceType
    subtype: str = Field(min_length=1, max_length=50, examples=["tractor"])
    description: str | None = Field(None, max_length=1000)
    daily_rate: float = Field(ge=0, description="INR per day")
    capacity_note: str | None = Field(None, max_length=200, examples=["45 HP"])
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class ResourceUpdate(BaseModel):
    subtype: str | None = Field(None, min_length=1, max_length=50)
    description: str | None = Field(None, max_length=1000)
    daily_rate: float | None = Field(None, ge=0)
    capacity_note: str | None = Field(None, max_length=200)
    lat: float | None = Field(None, ge=-90, le=90)
    lng: float | None = Field(None, ge=-180, le=180)
    is_active: bool | None = None

    @model_validator(mode="after")
    def lat_lng_together(self):
        if (self.lat is None) != (self.lng is None):
            raise ValueError("lat and lng must be provided together")
        return self


class ResourceOut(BaseModel):
    """Services must fill lat/lng (see geo_service.lat_lng) and distance_km for searches."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: ResourceType
    subtype: str
    description: str | None
    daily_rate: float
    capacity_note: str | None
    lat: float
    lng: float
    is_active: bool
    distance_km: float | None = None  # only set on search results
    created_at: datetime
    owner: UserPublic


class ResourceListResponse(BaseModel):
    items: list[ResourceOut]
    total: int
    limit: int
    offset: int