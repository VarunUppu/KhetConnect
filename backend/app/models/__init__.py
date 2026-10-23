# File: backend/app/models/__init__.py
from app.models.availability_slot import AvailabilitySlot
from app.models.booking import Booking
from app.models.otp_code import OtpCode
from app.models.rating import Rating
from app.models.resource import Resource
from app.models.user import User

__all__ = ["User", "Resource", "AvailabilitySlot", "Booking", "Rating", "OtpCode"]