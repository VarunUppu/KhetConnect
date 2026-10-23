# File: backend/app/routers/resources.py
import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.errors import not_implemented
from app.db import get_db
from app.deps import get_current_user
from app.models.user import User
from app.schemas.enums import ResourceType
from app.schemas.resource import (
    ResourceCreate,
    ResourceListResponse,
    ResourceOut,
    ResourceUpdate,
)

router = APIRouter(prefix="/resources", tags=["resources"])


@router.post("", response_model=ResourceOut, status_code=201)
def create_resource(
    body: ResourceCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    raise not_implemented("resources.create")


@router.get("", response_model=ResourceListResponse)
def search_resources(
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
    raise not_implemented("resources.search")


# NOTE: /mine must be declared BEFORE /{resource_id}.
@router.get("/mine", response_model=list[ResourceOut])
def my_resources(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    raise not_implemented("resources.mine")


@router.get("/{resource_id}", response_model=ResourceOut)
def get_resource(
    resource_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    raise not_implemented("resources.get")


@router.patch("/{resource_id}", response_model=ResourceOut)
def update_resource(
    resource_id: uuid.UUID,
    body: ResourceUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    raise not_implemented("resources.update")


@router.delete("/{resource_id}", status_code=204)
def delete_resource(
    resource_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Soft delete (is_active = false)."""
    raise not_implemented("resources.delete")