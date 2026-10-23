# File: backend/app/schemas/slot.py
import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, model_validator


class SlotCreate(BaseModel):
    start_date: date
    end_date: date  # inclusive

    @model_validator(mode="after")
    def check_range(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class SlotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    resource_id: uuid.UUID
    start_date: date
    end_date: date
    is_booked: bool