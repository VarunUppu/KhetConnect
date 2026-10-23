# File: backend/app/schemas/booking.py
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.enums import BookingStatus
from app.schemas.resource import ResourceOut
from app.schemas.slot import SlotOut
from app.schemas.user import UserPublic


class BookingCreate(BaseModel):
    resource_id: uuid.UUID
    slot_id: uuid.UUID
    task_description: str | None = Field(None, max_length=1000)


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: BookingStatus
    requested_at: datetime
    task_description: str | None
    resource: ResourceOut      # resource.owner is the provider
    slot: SlotOut
    requester: UserPublic
    # The OTHER party's phone number. Only non-null once status is accepted/completed.
    counterparty_phone: str | None = None


class BookingListResponse(BaseModel):
    items: list[BookingOut]
    total: int
    limit: int
    offset: int