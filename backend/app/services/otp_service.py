# File: backend/app/services/otp_service.py
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.models.otp_code import OtpCode
from app.services.sms_service import SMSDeliveryError, SMSGateway

OTP_LENGTH = 6
INVALID_OTP = "Invalid or expired OTP"


def generate_code() -> str:
    return f"{secrets.randbelow(10**OTP_LENGTH):0{OTP_LENGTH}d}"


def hash_code(phone_number: str, code: str) -> str:
    """HMAC keyed with the server secret and bound to the phone number (OTPs are never stored in plain text)."""
    key = settings.JWT_SECRET.encode()
    return hmac.new(key, f"{phone_number}:{code}".encode(), hashlib.sha256).hexdigest()


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def request_otp(db: Session, phone_number: str, gateway: SMSGateway) -> None:
    now = datetime.now(timezone.utc)

    latest = db.execute(
        select(OtpCode)
        .where(OtpCode.phone_number == phone_number)
        .order_by(OtpCode.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if latest is not None:
        elapsed = (now - _aware(latest.created_at)).total_seconds()
        if elapsed < settings.OTP_RESEND_COOLDOWN_SECONDS:
            wait = int(settings.OTP_RESEND_COOLDOWN_SECONDS - elapsed) + 1
            raise HTTPException(429, f"Please wait {wait} seconds before requesting another OTP")

    # Only the newest OTP is ever valid
    db.execute(
        update(OtpCode)
        .where(OtpCode.phone_number == phone_number, OtpCode.consumed.is_(False))
        .values(consumed=True)
    )

    code = generate_code()
    db.add(
        OtpCode(
            phone_number=phone_number,
            code_hash=hash_code(phone_number, code),
            expires_at=now + timedelta(seconds=settings.OTP_TTL_SECONDS),
        )
    )
    db.flush()

    try:
        gateway.send_otp(phone_number, code)
    except SMSDeliveryError:
        db.rollback()  # no usable OTP exists if it never left the server
        raise HTTPException(502, "Could not send OTP. Please try again.") from None

    db.commit()


def verify_otp(db: Session, phone_number: str, code: str) -> None:
    """Returns None on success; raises HTTPException(400/429) otherwise."""
    now = datetime.now(timezone.utc)

    otp = db.execute(
        select(OtpCode)
        .where(OtpCode.phone_number == phone_number, OtpCode.consumed.is_(False))
        .order_by(OtpCode.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if otp is None:
        raise HTTPException(400, INVALID_OTP)

    if _aware(otp.expires_at) <= now:
        otp.consumed = True
        db.commit()
        raise HTTPException(400, INVALID_OTP)

    if otp.attempts >= settings.OTP_MAX_ATTEMPTS:
        raise HTTPException(429, "Too many incorrect attempts. Request a new OTP.")

    if not hmac.compare_digest(otp.code_hash, hash_code(phone_number, code)):
        otp.attempts += 1
        db.commit()
        if otp.attempts >= settings.OTP_MAX_ATTEMPTS:
            raise HTTPException(429, "Too many incorrect attempts. Request a new OTP.")
        raise HTTPException(400, INVALID_OTP)

    otp.consumed = True
    db.commit()