# File: backend/app/routers/auth.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import settings
from app.deps import get_db
from app.schemas.auth import RequestOtpIn, RequestOtpOut, TokenOut, VerifyOtpIn
from app.services import auth_service, otp_service, user_service
from app.services.sms_service import SMSGateway, get_sms_gateway

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/request-otp", response_model=RequestOtpOut)
def request_otp(
    body: RequestOtpIn,
    db: Session = Depends(get_db),
    gateway: SMSGateway = Depends(get_sms_gateway),
):
    otp_service.request_otp(db, body.phone_number, gateway)
    return RequestOtpOut(message="OTP sent", expires_in_seconds=settings.OTP_TTL_SECONDS)


@router.post("/verify-otp", response_model=TokenOut)
def verify_otp(body: VerifyOtpIn, db: Session = Depends(get_db)):
    otp_service.verify_otp(db, body.phone_number, body.otp)
    user, is_new = auth_service.get_or_create_user(db, body.phone_number)
    token, expires_in = auth_service.create_access_token(user.id)
    return TokenOut(
        access_token=token,
        expires_in=expires_in,
        is_new_user=is_new,
        user=user_service.to_private(user),
    )