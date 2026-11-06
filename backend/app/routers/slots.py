# File: backend/app/routers/slots.py
import uuid
from datetime import date

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models.user import User
from app.schemas.slot import SlotCreate, SlotOut
from app.services import resource_service

router = APIRouter(prefix="/resources/{resource_id}/availability", tags=["availability"])


@router.post("", response_model=SlotOut, status_code=201)
def create_slot(
    resource_id: uuid.UUID,
    body: SlotCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return resource_service.create_slot(db, user, resource_id, body)


@router.get("", response_model=list[SlotOut])
def list_slots(
    resource_id: uuid.UUID,
    from_date: date | None = None,
    to_date: date | None = None,
    only_available: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return resource_service.list_slots(db, user, resource_id, from_date, to_date, only_available)


@router.delete("/{slot_id}", status_code=204)
def delete_slot(
    resource_id: uuid.UUID,
    slot_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    resource_service.delete_slot(db, user, resource_id, slot_id)
    return Response(status_code=204)