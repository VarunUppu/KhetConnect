# File: backend/app/models/user.py
import uuid
from datetime import datetime
from decimal import Decimal

from geoalchemy2 import Geography
from sqlalchemy import DateTime, Integer, Numeric, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    phone_number: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    # farmer | provider | both  (enforced by a CHECK constraint in 001_init.sql)
    role: Mapped[str] = mapped_column(String, nullable=False, default="farmer", server_default="farmer")
    village: Mapped[str | None] = mapped_column(String, nullable=True)
    district: Mapped[str | None] = mapped_column(String, nullable=True)
    # spatial_index=False because the migration already creates the GiST index
    location = mapped_column(Geography(geometry_type="POINT", srid=4326, spatial_index=False), nullable=True)
    language_pref: Mapped[str] = mapped_column(String, nullable=False, default="hi", server_default="hi")
    trust_score: Mapped[Decimal] = mapped_column(
        Numeric(3, 2), nullable=False, default=Decimal("0"), server_default="0"
    )
    rating_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )