# File: backend/app/services/sms_service.py
"""SMS gateway abstraction.

The auth logic only knows about `SMSGateway`. To add a real provider (MSG91, Twilio, ...):

    class Msg91Gateway(SMSGateway):
        def send_otp(self, phone_number: str, code: str) -> None:
            # call the provider; raise SMSDeliveryError on failure
            ...

    register_gateway("msg91", Msg91Gateway)

then set SMS_PROVIDER=msg91 in .env. Nothing in otp_service or the routers changes.
"""
from abc import ABC, abstractmethod
from typing import Callable

from app.config import settings

OTP_MESSAGE_TEMPLATE = "Your KhetConnect OTP is {code}. It is valid for {minutes} minutes. Do not share it."


class SMSDeliveryError(Exception):
    """Raised by a gateway when the SMS could not be handed to the provider."""


class SMSGateway(ABC):
    @abstractmethod
    def send_otp(self, phone_number: str, code: str) -> None:
        """Deliver `code` to `phone_number` (E.164). Raise SMSDeliveryError on failure."""


def build_otp_message(code: str) -> str:
    return OTP_MESSAGE_TEMPLATE.format(code=code, minutes=settings.OTP_TTL_SECONDS // 60)


class ConsoleSMSGateway(SMSGateway):
    """Dev stub: prints the OTP to the server log instead of sending an SMS."""

    def send_otp(self, phone_number: str, code: str) -> None:
        print(f"[SMS:console] to {phone_number}: {build_otp_message(code)}", flush=True)


_REGISTRY: dict[str, Callable[[], SMSGateway]] = {"console": ConsoleSMSGateway}


def register_gateway(name: str, factory: Callable[[], SMSGateway]) -> None:
    _REGISTRY[name.lower()] = factory


def get_sms_gateway() -> SMSGateway:
    """FastAPI dependency. Tests override this to capture OTPs."""
    name = settings.SMS_PROVIDER.lower()
    try:
        return _REGISTRY[name]()
    except KeyError:
        raise RuntimeError(
            f"Unknown SMS_PROVIDER '{settings.SMS_PROVIDER}'. Registered: {sorted(_REGISTRY)}"
        ) from None