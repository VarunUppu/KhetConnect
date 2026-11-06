# File: backend/app/routers/resources.py
import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_complete_profile
from app.models.user import User
from app.schemas.enums import ResourceType
from app.schemas.resource import (
    ResourceCreate,
    ResourceListResponse,
    ResourceOut,
    ResourceUpdate,
)
from app.services import resource_service

router = APIRouter(prefix="/resources", tags=["resources"])

# ROUTE ORDER MATTERS: FastAPI matches in declaration order. The literal paths /discover and
# /mine MUST come before /{resource_id}, otherwise "discover" would be parsed as a UUID (422).


@router.post("", response_model=ResourceOut, status_code=201)
def create_resource(
    body: ResourceCreate,
    user: User = Depends(require_complete_profile),
    db: Session = Depends(get_db),
):
    return resource_service.create_resource(db, user, body)


@router.get("/discover", response_model=ResourceListResponse)
def discover_resources(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(25, gt=0, le=200),
    type: ResourceType | None = None,
    subtype: str | None = None,
    max_daily_rate: float | None = Query(None, ge=0),
    available_from: date | None = None,
    available_to: date | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items, total = resource_service.discover(
        db,
        viewer_id=user.id,
        lat=lat,
        lng=lng,
        radius_m=radius_km * 1000.0,  # API speaks km, PostGIS geography speaks metres
        resource_type=type.value if type else None,
        subtype=subtype,
        max_daily_rate=max_daily_rate,
        available_from=available_from,
        available_to=available_to,
        limit=limit,
        offset=offset,
    )
    return ResourceListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/mine", response_model=list[ResourceOut])
def my_resources(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return resource_service.my_resources(db, user)


@router.get("/{resource_id}", response_model=ResourceOut)
def get_resource(
    resource_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return resource_service.get_resource(db, user, resource_id)


@router.patch("/{resource_id}", response_model=ResourceOut)
@router.put("/{resource_id}", response_model=ResourceOut)  # alias: identical partial-update behaviour
def update_resource(
    resource_id: uuid.UUID,
    body: ResourceUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return resource_service.update_resource(db, user, resource_id, body)


@router.delete("/{resource_id}", status_code=204)
def delete_resource(
    resource_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Soft delete (is_active = false)."""
    resource_service.soft_delete_resource(db, user, resource_id)
    return Response(status_code=204)