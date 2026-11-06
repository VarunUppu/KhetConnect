# File: backend/app/services/resource_service.py
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.availability_slot import AvailabilitySlot
from app.models.booking import Booking
from app.models.resource import Resource
from app.models.user import User
from app.schemas.resource import ResourceCreate, ResourceOut, ResourceUpdate
from app.schemas.slot import SlotCreate
from app.schemas.user import UserPublic
from app.services.geo_service import geog_point, lat_lng, make_point

_IST = timezone(timedelta(hours=5, minutes=30))
_PROVIDER_ROLES = ("provider", "both")
_ACTIVE_BOOKING_STATES = ("pending", "accepted")


# ------------------------------------------------------------------ helpers

def _today_ist() -> date:
    """'Today' for Indian users, regardless of the server's timezone."""
    return datetime.now(_IST).date()


def _norm_subtype(value: str) -> str:
    """Subtypes are lower_snake_case so that filters match exactly ('Tractor ' -> 'tractor')."""
    return value.strip().lower().replace(" ", "_")


def _to_out(resource: Resource, owner: User, distance_m: float | None = None) -> ResourceOut:
    lat, lng = lat_lng(resource.location)
    return ResourceOut(
        id=resource.id,
        type=resource.type,
        subtype=resource.subtype,
        description=resource.description,
        daily_rate=float(resource.daily_rate),
        capacity_note=resource.capacity_note,
        lat=lat,
        lng=lng,
        is_active=resource.is_active,
        distance_km=None if distance_m is None else round(distance_m / 1000.0, 3),
        created_at=resource.created_at,
        owner=UserPublic.model_validate(owner),
    )


def _get_owned(db: Session, owner: User, resource_id: uuid.UUID) -> Resource:
    """404 if missing, 403 if it belongs to someone else."""
    resource = db.get(Resource, resource_id)
    if resource is None:
        raise HTTPException(404, "Resource not found")
    if resource.owner_id != owner.id:
        raise HTTPException(403, "You do not own this resource")
    return resource


def _get_visible(db: Session, viewer: User, resource_id: uuid.UUID) -> Resource:
    """Inactive (soft-deleted) resources are visible to their owner only."""
    resource = db.get(Resource, resource_id)
    if resource is None or (not resource.is_active and resource.owner_id != viewer.id):
        raise HTTPException(404, "Resource not found")
    return resource


# ------------------------------------------------------------------ discovery

def discover(
    db: Session,
    *,
    viewer_id: uuid.UUID,
    lat: float,
    lng: float,
    radius_m: float,
    resource_type: str | None = None,
    subtype: str | None = None,
    max_daily_rate: float | None = None,
    available_from: date | None = None,
    available_to: date | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[ResourceOut], int]:
    """Radius search: active resources within `radius_m` METRES of (lat, lng), nearest first.

    ======================= THE POSTGIS QUERY (for the viva) =======================

        SELECT r.*, u.*, ST_Distance(r.location, :centre) AS distance_m
        FROM   resources r JOIN users u ON u.id = r.owner_id
        WHERE  r.is_active
          AND  r.owner_id <> :viewer              -- don't show me my own listings
          AND  u.role IN ('provider','both')      -- owner still offers services
          AND  ST_DWithin(r.location, :centre, :radius_m)
        ORDER  BY distance_m, r.id
        LIMIT  :limit OFFSET :offset

    where :centre = ST_GeogFromText('SRID=4326;POINT(<lng> <lat>)').

    Why each piece:

    1. GEOGRAPHY, not GEOMETRY. resources.location is geography(Point,4326). PostGIS
       measures geography on the WGS84 spheroid, so distances are in METRES. The same
       numbers as geometry(4326) would be in DEGREES, and one degree of longitude is not
       a fixed length, so a "5 km" radius would be wrong.

    2. ST_DWithin(a, b, d) is the FILTER. It is true when distance(a, b) <= d, so a listing
       exactly at the radius IS included (inclusive boundary). It is preferred over
       `ST_Distance(a, b) <= d` because ST_DWithin can use the GiST spatial index on
       resources.location: the index first narrows to listings whose bounding box is near
       the centre, and only those get an exact distance check. ST_Distance in a WHERE
       clause would be computed for every row (a sequential scan).

    3. ST_Distance(a, b) is the SORT KEY and the value returned as distance_km (/1000). It
       is only evaluated for rows that passed the filter.

    4. ORDER BY distance_m, r.id. The id is a tie-breaker. Without it two listings at
       identical distance could swap places between page 1 and page 2, causing duplicates
       or gaps when paginating. LIMIT/OFFSET implement the pagination.

    5. total comes from a second COUNT(*) with the SAME WHERE clause (no LIMIT), so the
       app can show "47 results" and know when to stop loading pages.

    6. Coordinate order: WKT is POINT(lng lat), i.e. X (longitude) first. Swapping them is
       the classic PostGIS bug; geog_point() in geo_service.py is the single place that
       does this.

    available_from/to: a listing qualifies only if ONE unbooked slot fully covers the whole
    requested range (slot.start_date <= from AND slot.end_date >= to), via EXISTS.
    """
    if available_from or available_to:
        start = available_from or available_to
        end = available_to or available_from
        if end < start:
            raise HTTPException(422, "available_to must be on or after available_from")

    centre = geog_point(lat, lng)
    distance_m = func.ST_Distance(Resource.location, centre).label("distance_m")

    conditions = [
        Resource.is_active.is_(True),
        Resource.owner_id != viewer_id,
        User.role.in_(_PROVIDER_ROLES),
        func.ST_DWithin(Resource.location, centre, radius_m),
    ]
    if resource_type:
        conditions.append(Resource.type == resource_type)
    if subtype:
        conditions.append(Resource.subtype == _norm_subtype(subtype))
    if max_daily_rate is not None:
        conditions.append(Resource.daily_rate <= max_daily_rate)
    if available_from or available_to:
        conditions.append(
            exists()
            .where(
                AvailabilitySlot.resource_id == Resource.id,
                AvailabilitySlot.is_booked.is_(False),
                AvailabilitySlot.start_date <= start,
                AvailabilitySlot.end_date >= end,
            )
            .correlate(Resource)
        )

    rows = db.execute(
        select(Resource, User, distance_m)
        .join(User, User.id == Resource.owner_id)
        .where(*conditions)
        .order_by(distance_m, Resource.id)
        .limit(limit)
        .offset(offset)
    ).all()

    total = db.execute(
        select(func.count())
        .select_from(Resource)
        .join(User, User.id == Resource.owner_id)
        .where(*conditions)
    ).scalar_one()

    return [_to_out(res, owner, dist) for res, owner, dist in rows], total


# ------------------------------------------------------------------ resources CRUD

def create_resource(db: Session, owner: User, data: ResourceCreate) -> ResourceOut:
    """Role must be provider/both (403). Complete profile is enforced by the router dependency."""
    if owner.role not in _PROVIDER_ROLES:
        raise HTTPException(403, "Set your role to 'provider' or 'both' to list equipment or labor")

    resource = Resource(
        owner_id=owner.id,
        type=getattr(data.type, "value", data.type),
        subtype=_norm_subtype(data.subtype),
        description=(data.description or "").strip() or None,
        daily_rate=Decimal(str(data.daily_rate)),
        capacity_note=(data.capacity_note or "").strip() or None,
        location=make_point(data.lat, data.lng),
    )
    db.add(resource)
    db.commit()
    db.refresh(resource)  # loads created_at and the stored location
    return _to_out(resource, owner)


def my_resources(db: Session, owner: User) -> list[ResourceOut]:
    rows = db.scalars(
        select(Resource).where(Resource.owner_id == owner.id).order_by(Resource.created_at.desc())
    ).all()
    return [_to_out(r, owner) for r in rows]


def get_resource(db: Session, viewer: User, resource_id: uuid.UUID) -> ResourceOut:
    resource = _get_visible(db, viewer, resource_id)
    owner = db.get(User, resource.owner_id)
    return _to_out(resource, owner)


def update_resource(
    db: Session, owner: User, resource_id: uuid.UUID, data: ResourceUpdate
) -> ResourceOut:
    """Owner only. Omitted/null fields are unchanged (same rule as PATCH /users/me)."""
    resource = _get_owned(db, owner, resource_id)
    changes = data.model_dump(exclude_none=True)

    if "subtype" in changes:
        resource.subtype = _norm_subtype(changes["subtype"])
    if "description" in changes:
        resource.description = changes["description"].strip() or None
    if "daily_rate" in changes:
        resource.daily_rate = Decimal(str(changes["daily_rate"]))
    if "capacity_note" in changes:
        resource.capacity_note = changes["capacity_note"].strip() or None
    if "lat" in changes and "lng" in changes:
        resource.location = make_point(changes["lat"], changes["lng"])
    if "is_active" in changes:
        resource.is_active = changes["is_active"]

    db.commit()
    db.refresh(resource)
    return _to_out(resource, owner)


def soft_delete_resource(db: Session, owner: User, resource_id: uuid.UUID) -> None:
    """Owner only; sets is_active=false. 409 if pending/accepted bookings exist."""
    resource = _get_owned(db, owner, resource_id)
    blocked = db.execute(
        select(
            exists().where(
                Booking.resource_id == resource.id,
                Booking.status.in_(_ACTIVE_BOOKING_STATES),
            )
        )
    ).scalar()
    if blocked:
        raise HTTPException(409, "Resource has pending or accepted bookings")
    resource.is_active = False
    db.commit()


# ------------------------------------------------------------------ availability slots

def create_slot(
    db: Session, owner: User, resource_id: uuid.UUID, data: SlotCreate
) -> AvailabilitySlot:
    """Owner only. Start in the past -> 422. Overlap -> 409 (enforced by the DB exclusion constraint,
    which is race-free; a Python pre-check could be fooled by two simultaneous requests)."""
    resource = _get_owned(db, owner, resource_id)
    if data.start_date < _today_ist():
        raise HTTPException(422, "start_date cannot be in the past")

    slot = AvailabilitySlot(
        resource_id=resource.id, start_date=data.start_date, end_date=data.end_date
    )
    db.add(slot)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if getattr(exc.orig, "pgcode", None) == "23P01":  # exclusion_violation
            raise HTTPException(409, "This date range overlaps an existing slot") from None
        raise
    db.refresh(slot)
    return slot


def list_slots(
    db: Session,
    viewer: User,
    resource_id: uuid.UUID,
    from_date: date | None = None,
    to_date: date | None = None,
    only_available: bool = False,
) -> list[AvailabilitySlot]:
    """Any logged-in user may view slots of an active resource. Returns booked AND free slots
    unless only_available=True. from_date/to_date keep slots that OVERLAP that window."""
    resource = _get_visible(db, viewer, resource_id)
    stmt = select(AvailabilitySlot).where(AvailabilitySlot.resource_id == resource.id)
    if only_available:
        stmt = stmt.where(AvailabilitySlot.is_booked.is_(False))
    if from_date:
        stmt = stmt.where(AvailabilitySlot.end_date >= from_date)
    if to_date:
        stmt = stmt.where(AvailabilitySlot.start_date <= to_date)
    return list(db.scalars(stmt.order_by(AvailabilitySlot.start_date)).all())


def delete_slot(db: Session, owner: User, resource_id: uuid.UUID, slot_id: uuid.UUID) -> None:
    """Owner only; 409 if the slot is booked or has live bookings."""
    resource = _get_owned(db, owner, resource_id)
    slot = db.get(AvailabilitySlot, slot_id)
    if slot is None or slot.resource_id != resource.id:
        raise HTTPException(404, "Slot not found")

    has_bookings = db.execute(
        select(
            exists().where(
                Booking.slot_id == slot.id,
                Booking.status.in_(("pending", "accepted", "completed")),
            )
        )
    ).scalar()
    if slot.is_booked or has_bookings:
        raise HTTPException(409, "Slot is booked or has pending bookings")

    try:
        db.delete(slot)
        db.commit()
    except IntegrityError:  # e.g. old rejected/cancelled bookings still reference the slot
        db.rollback()
        raise HTTPException(409, "Slot has booking history and cannot be deleted") from None