# File: backend/app/services/booking_service.py
from sqlalchemy.orm import Session

# Allowed transitions (Stage 3):
#   pending   -> accepted   (owner)
#   pending   -> rejected   (owner)
#   pending   -> cancelled  (requester)
#   accepted  -> cancelled  (requester or owner)  -> frees slot (is_booked = false)
#   accepted  -> completed  (owner, on/after slot.start_date)
# On accept: set slot.is_booked = true and auto-reject other pending bookings for that slot.
# Run each transition inside one transaction and lock rows (SELECT ... FOR UPDATE) to avoid races.


def create_booking(db: Session, requester, data):
    """Stage 3. Resource active; slot belongs to resource and is not booked (409);
    requester != owner (403); requester profile complete."""
    raise NotImplementedError


def transition_booking(db: Session, actor, booking_id, action: str):
    """Stage 3. action in {accept, reject, cancel, complete}; invalid transition -> 409."""
    raise NotImplementedError


def list_bookings(db: Session, user, role, status, limit: int, offset: int):
    """Stage 3."""
    raise NotImplementedError


def to_booking_out(db: Session, booking, viewer):
    """Stage 3. Sets counterparty_phone only when status in (accepted, completed)."""
    raise NotImplementedError