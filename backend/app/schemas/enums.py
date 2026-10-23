# File: backend/app/schemas/enums.py
from enum import Enum


class UserRole(str, Enum):
    farmer = "farmer"
    provider = "provider"
    both = "both"


class ResourceType(str, Enum):
    equipment = "equipment"
    labor = "labor"


class BookingStatus(str, Enum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"
    completed = "completed"
    cancelled = "cancelled"


class BookingRole(str, Enum):
    requester = "requester"  # bookings I made
    owner = "owner"          # bookings made on my resources