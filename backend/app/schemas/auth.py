# File: backend/app/schemas/auth.py
import re

from pydantic import BaseModel, Field, field_validator

from app.schemas.user import UserPrivate

_PHONE_RE = re.compile(r"^\+91[6-9]\d{9}$")


def normalize_phone(value: str) -> str:
    cleaned = re.sub(r"[\s\-]", "", value)
    if not _PHONE_RE.fullmatch(cleaned):
        raise ValueError("Phone number must be an Indian mobile number like +919876543210")
    return cleaned


class RequestOtpIn(BaseModel):
    phone_number: str

    @field_validator("phone_number")
    @classmethod
    def _check_phone(cls, v: str) -> str:
        return normalize_phone(v)


class RequestOtpOut(BaseModel):
    message: str
    expires_in_seconds: int


class VerifyOtpIn(BaseModel):
    phone_number: str
    otp: str = Field(pattern=r"^\d{6}$")

    @field_validator("phone_number")
    @classmethod
    def _check_phone(cls, v: str) -> str:
        return normalize_phone(v)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    is_new_user: bool
    user: UserPrivate