# File: backend/app/routers/bookings.py
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.errors import not_implemented
from app.db import get_db
from app.deps import get_current_user
from app.models.user import User
from app.schemas.booking import BookingCreate, BookingListResponse, BookingOut
from app.schemas.enums import BookingRole, BookingStatus

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.post("", response_model=BookingOut, status_code=201)
def create_booking(
    body: BookingCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    raise not_implemented("bookings.create")


@router.get("", response_model=BookingListResponse)
def list_bookings(
    role: BookingRole = BookingRole.requester,
    status_filter: BookingStatus | None = Query(None, alias="status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    raise not_implemented("bookings.list")


@router.get("/{booking_id}", response_model=BookingOut)
def get_booking(
    booking_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    raise not_implemented("bookings.get")


@router.post("/{booking_id}/accept", response_model=BookingOut)
def accept_booking(
    booking_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    raise not_implemented("bookings.accept")


@router.post("/{booking_id}/reject", response_model=BookingOut)
def reject_booking(
    booking_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    raise not_implemented("bookings.reject")


@router.post("/{booking_id}/cancel", response_model=BookingOut)
def cancel_booking(
    booking_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    raise not_implemented("bookings.cancel")


@router.post("/{booking_id}/complete", response_model=BookingOut)
def complete_booking(
    booking_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    raise not_implemented("bookings.complete")