# File: backend/tests/test_auth.py
"""Auth tests. Run from backend/ with:  python -m pytest -v

* JWT / hashing / validation tests need no database.
* OTP-flow and profile tests need Postgres running (docker compose up -d) with 001_init.sql applied;
  they are skipped automatically if the database is unreachable.
* No real SMS is sent: the SMS gateway dependency is replaced with a capturing fake.
"""
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.config import settings
from app.db import engine
from app.main import app
from app.services import auth_service, otp_service
from app.services.auth_service import TokenError
from app.services.sms_service import SMSGateway, get_sms_gateway

API = "/api/v1"
PHONE_A = "+919000000001"
PHONE_B = "+919000000002"
TEST_PHONES = [PHONE_A, PHONE_B]


# ---------------------------------------------------------------- fixtures

class CapturingGateway(SMSGateway):
    def __init__(self):
        self.codes: dict[str, str] = {}

    def send_otp(self, phone_number: str, code: str) -> None:
        self.codes[phone_number] = code


@pytest.fixture
def gateway():
    return CapturingGateway()


@pytest.fixture
def app_client(gateway):
    """Client that needs no database."""
    app.dependency_overrides[get_sms_gateway] = lambda: gateway
    yield TestClient(app)
    app.dependency_overrides.clear()


def _cleanup():
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM otp_codes WHERE phone_number = ANY(:p)"), {"p": TEST_PHONES})
        conn.execute(text("DELETE FROM users WHERE phone_number = ANY(:p)"), {"p": TEST_PHONES})


@pytest.fixture
def client(app_client):
    """Client backed by the real database; skips if Postgres is down."""
    try:
        _cleanup()
    except OperationalError:
        pytest.skip("Postgres not reachable (docker compose up -d)")
    yield app_client
    _cleanup()


@pytest.fixture
def no_cooldown(monkeypatch):
    monkeypatch.setattr(settings, "OTP_RESEND_COOLDOWN_SECONDS", 0)


# ---------------------------------------------------------------- helpers

def request_otp(client, phone):
    return client.post(f"{API}/auth/request-otp", json={"phone_number": phone})


def verify(client, phone, otp):
    return client.post(f"{API}/auth/verify-otp", json={"phone_number": phone, "otp": otp})


def login(client, gateway, phone):
    assert request_otp(client, phone).status_code == 200
    r = verify(client, phone, gateway.codes[phone])
    assert r.status_code == 200, r.text
    return r.json()


def auth_header(body):
    return {"Authorization": f"Bearer {body['access_token']}"}


def wrong_code(real):
    return "000000" if real != "000000" else "111111"


def _token(payload, secret=None, algorithm="HS256"):
    return jwt.encode(payload, secret or settings.JWT_SECRET, algorithm=algorithm)


def _claims(**overrides):
    now = datetime.now(timezone.utc)
    claims = {"sub": str(uuid.uuid4()), "iat": now, "exp": now + timedelta(hours=1)}
    claims.update(overrides)
    return claims


# ---------------------------------------------------------------- JWT (no DB)

def test_token_roundtrip():
    uid = uuid.uuid4()
    token, expires_in = auth_service.create_access_token(uid)
    assert expires_in == settings.ACCESS_TOKEN_EXPIRE_DAYS * 86400
    assert auth_service.decode_access_token(token) == uid


def test_expired_token_rejected():
    token = _token(_claims(exp=datetime.now(timezone.utc) - timedelta(hours=1)))
    with pytest.raises(TokenError):
        auth_service.decode_access_token(token)


def test_wrong_signature_rejected():
    with pytest.raises(TokenError):
        auth_service.decode_access_token(_token(_claims(), secret="x" * 40))


@pytest.mark.parametrize("garbage", ["", "not.a.jwt", "abc"])
def test_garbage_token_rejected(garbage):
    with pytest.raises(TokenError):
        auth_service.decode_access_token(garbage)


def test_token_without_exp_rejected():
    claims = _claims()
    del claims["exp"]
    with pytest.raises(TokenError):
        auth_service.decode_access_token(_token(claims))


def test_non_uuid_subject_rejected():
    with pytest.raises(TokenError):
        auth_service.decode_access_token(_token(_claims(sub="not-a-uuid")))


def test_alg_none_rejected():
    token = jwt.encode(_claims(), key=None, algorithm="none")
    with pytest.raises(TokenError):
        auth_service.decode_access_token(token)


# ---------------------------------------------------------------- OTP helpers (no DB)

def test_generate_code_is_six_digits():
    for _ in range(200):
        code = otp_service.generate_code()
        assert len(code) == 6 and code.isdigit()


def test_hash_is_deterministic_and_bound_to_phone():
    assert otp_service.hash_code(PHONE_A, "123456") == otp_service.hash_code(PHONE_A, "123456")
    assert otp_service.hash_code(PHONE_A, "123456") != otp_service.hash_code(PHONE_B, "123456")
    assert "123456" not in otp_service.hash_code(PHONE_A, "123456")


# ---------------------------------------------------------------- API validation / guard (no DB)

def test_protected_route_without_token_is_401(app_client):
    r = app_client.get(f"{API}/users/me")
    assert r.status_code == 401
    assert r.headers.get("www-authenticate") == "Bearer"


def test_protected_route_with_bad_token_is_401(app_client):
    r = app_client.get(f"{API}/users/me", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401


@pytest.mark.parametrize("phone", ["9876543210", "+919876", "+11234567890", "+915876543210", "abc"])
def test_request_otp_rejects_bad_phone(app_client, phone):
    assert request_otp(app_client, phone).status_code == 422


@pytest.mark.parametrize("otp", ["12345", "1234567", "12ab56", ""])
def test_verify_otp_rejects_bad_format(app_client, otp):
    assert verify(app_client, PHONE_A, otp).status_code == 422


# ---------------------------------------------------------------- OTP flow (DB)

def test_full_login_flow_and_second_login(client, gateway, no_cooldown):
    first = login(client, gateway, PHONE_A)
    assert first["is_new_user"] is True
    assert first["token_type"] == "bearer"
    assert first["user"]["phone_number"] == PHONE_A
    assert first["user"]["role"] == "farmer"
    assert first["user"]["profile_complete"] is False
    assert auth_service.decode_access_token(first["access_token"]) == uuid.UUID(first["user"]["id"])

    me = client.get(f"{API}/users/me", headers=auth_header(first))
    assert me.status_code == 200 and me.json()["phone_number"] == PHONE_A

    second = login(client, gateway, PHONE_A)
    assert second["is_new_user"] is False
    assert second["user"]["id"] == first["user"]["id"]


def test_wrong_otp_is_400(client, gateway):
    request_otp(client, PHONE_A)
    assert verify(client, PHONE_A, wrong_code(gateway.codes[PHONE_A])).status_code == 400


def test_verify_without_request_is_400(client):
    assert verify(client, PHONE_A, "123456").status_code == 400


def test_too_many_wrong_attempts_locks_out(client, gateway):
    request_otp(client, PHONE_A)
    real = gateway.codes[PHONE_A]
    bad = wrong_code(real)
    statuses = [verify(client, PHONE_A, bad).status_code for _ in range(settings.OTP_MAX_ATTEMPTS)]
    assert statuses[:-1] == [400] * (settings.OTP_MAX_ATTEMPTS - 1)
    assert statuses[-1] == 429
    assert verify(client, PHONE_A, real).status_code == 429  # even the right code is now refused


def test_otp_is_single_use(client, gateway):
    request_otp(client, PHONE_A)
    code = gateway.codes[PHONE_A]
    assert verify(client, PHONE_A, code).status_code == 200
    assert verify(client, PHONE_A, code).status_code == 400


def test_expired_otp_is_400(client, gateway):
    request_otp(client, PHONE_A)
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE otp_codes SET expires_at = now() - interval '1 minute' WHERE phone_number = :p"),
            {"p": PHONE_A},
        )
    assert verify(client, PHONE_A, gateway.codes[PHONE_A]).status_code == 400


def test_resend_cooldown_is_429(client):
    assert request_otp(client, PHONE_A).status_code == 200
    assert request_otp(client, PHONE_A).status_code == 429


def test_new_otp_invalidates_old_one(client, gateway, no_cooldown):
    request_otp(client, PHONE_A)
    old = gateway.codes[PHONE_A]
    request_otp(client, PHONE_A)
    new = gateway.codes[PHONE_A]
    if old != new:  # 1-in-a-million collision guard
        assert verify(client, PHONE_A, old).status_code == 400
    assert verify(client, PHONE_A, new).status_code == 200


# ---------------------------------------------------------------- profile (DB)

def test_put_and_patch_profile(client, gateway):
    body = login(client, gateway, PHONE_A)
    headers = auth_header(body)

    r = client.put(
        f"{API}/users/me",
        headers=headers,
        json={
            "name": "  Ramesh  ", "role": "both", "village": "Shamirpet", "district": "Medchal",
            "lat": 17.58, "lng": 78.57, "language_pref": "te",
        },
    )
    assert r.status_code == 200, r.text
    user = r.json()
    assert user["name"] == "Ramesh"  # trimmed
    assert user["role"] == "both"
    assert user["language_pref"] == "te"
    assert user["profile_complete"] is True
    assert user["lat"] == pytest.approx(17.58) and user["lng"] == pytest.approx(78.57)

    r = client.patch(f"{API}/users/me", headers=headers, json={"village": "Keesara"})
    assert r.status_code == 200
    assert r.json()["village"] == "Keesara"
    assert r.json()["name"] == "Ramesh"  # untouched
    assert r.json()["lat"] == pytest.approx(17.58)


def test_profile_lat_without_lng_is_422(client, gateway):
    body = login(client, gateway, PHONE_A)
    r = client.put(f"{API}/users/me", headers=auth_header(body), json={"lat": 17.5})
    assert r.status_code == 422


@pytest.mark.parametrize(
    "payload",
    [{"role": "admin"}, {"language_pref": "xx"}, {"lat": 95, "lng": 78}, {"name": "   "}, {"phone_number": "+919111111111"}],
)
def test_profile_invalid_values_are_422(client, gateway, payload):
    body = login(client, gateway, PHONE_A)
    assert client.put(f"{API}/users/me", headers=auth_header(body), json=payload).status_code == 422


def test_other_users_profile_is_public_only(client, gateway, no_cooldown):
    a = login(client, gateway, PHONE_A)
    b = login(client, gateway, PHONE_B)
    r = client.get(f"{API}/users/{a['user']['id']}", headers=auth_header(b))
    assert r.status_code == 200
    assert "phone_number" not in r.json() and "lat" not in r.json()
    assert client.get(f"{API}/users/{uuid.uuid4()}", headers=auth_header(b)).status_code == 404