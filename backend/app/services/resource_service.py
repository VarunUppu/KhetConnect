# File: backend/app/services/resource_service.py
from sqlalchemy.orm import Session


def search_nearby(db: Session, **filters):
    """Stage 2. Radius search on resources.location. Intended query shape:

        WHERE r.is_active
          AND ST_DWithin(r.location, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, :radius_m)
        ORDER BY ST_Distance(r.location, <same point>)   -- metres; divide by 1000 for distance_km

    ST_DWithin on geography uses the GiST index. Exclude the caller's own resources.
    available_from/to: require an unbooked slot with start_date <= from AND end_date >= to.
    """
    raise NotImplementedError


def create_resource(db: Session, owner, data):
    """Stage 2. Owner must have role provider/both and a complete profile (403 otherwise)."""
    raise NotImplementedError


def update_resource(db: Session, owner, resource_id, data):
    """Stage 2. Owner only."""
    raise NotImplementedError


def soft_delete_resource(db: Session, owner, resource_id):
    """Stage 2. Owner only; 409 if pending/accepted bookings exist."""
    raise NotImplementedError


def create_slot(db: Session, owner, resource_id, data):
    """Stage 2. Owner only; start_date not in the past; overlap -> 409 (DB exclusion constraint)."""
    raise NotImplementedError


def delete_slot(db: Session, owner, resource_id, slot_id):
    """Stage 2. Owner only; 409 if slot is booked or has pending bookings."""
    raise NotImplementedError