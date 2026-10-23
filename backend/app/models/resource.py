# File: backend/app/models/resource.py
import uuid
from datetime import datetime
from decimal import Decimal

from geoalchemy2 import Geography
from geoalchemy2.elements import WKBElement
from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, uuid_pk


class Resource(Base):
    __tablename__ = "resources"

    id: Mapped[uuid.UUID] = uuid_pk()
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(10), nullable=False)  # equipment | labor
    subtype: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    daily_rate: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    capacity_note: Mapped[str | None] = mapped_column(String(200))
    location: Mapped[WKBElement] = mapped_column(
        Geography("POINT", srid=4326, spatial_index=False), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )