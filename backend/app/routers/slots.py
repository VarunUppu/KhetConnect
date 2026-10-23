# File: backend/app/routers/slots.py
import uuid
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.errors import not_implemented
from app.db import get_db
from app.deps import get_current_user
from app.models.user import User
from app.schemas.slot import SlotCreate, SlotOut

router = APIRouter(prefix="/resources/{resource_id}/slots", tags=["slots"])


@router.post("", response_model=SlotOut, status_code=201)
def create_slot(
    resource_id: uuid.UUID,
    body: SlotCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    raise not_implemented("slots.create")


@router.get("", response_model=list[SlotOut])
def list_slots(
    resource_id: uuid.UUID,
    from_date: date | None = None,
    to_date: date | None = None,
    only_available: bool = True,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    raise not_implemented("slots.list")


@router.delete("/{slot_id}", status_code=204)
def delete_slot(
    resource_id: uuid.UUID,
    slot_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    raise not_implemented("slots.delete")