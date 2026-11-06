# File: backend/tests/test_resources.py
"""Stage 2 tests (listings, availability, radius discovery).

Run from backend/ with:  python -m pytest -v
All tests need Postgres + PostGIS (docker compose up -d, 001_init.sql applied); they are
skipped automatically if the database is unreachable. No real SMS is sent.

Test geography (all on the same meridian, lng 78.4867, Hyderabad):
    A = 17.3850   (search centre)
    B = 17.4300   ~4.98 km north of A  (0.045 deg of latitude ~ 110.67 km/deg * 0.045)
    C = 17.4750   ~9.96 km north of A
"""
import uuid
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.config import settings
from app.db import SessionLocal, engine
from app.main import app
from app.services import resource_service
from app.services.sms_service import SMSGateway, get_sms_gateway

API = "/api/v1"
OWNER = "+919000000011"
VIEWER = "+919000000012"
NEWBIE = "+919000000013"  # never completes a profile
MANUAL_TEST_PHONES = ["+919876500001", "+919876500002"]
TEST_PHONES = [OWNER, VIEWER, NEWBIE] + MANUAL_TEST_PHONES

LNG = 78.4867
A = (17.3850, LNG)
B = (17.4300, LNG)
C = (17.4750, LNG)


# ---------------------------------------------------------------- fixtures / helpers

class CapturingGateway(SMSGateway):
    def __init__(self):
        self.codes: dict[str, str] = {}

    def send_otp(self, phone_number: str, code: str) -> None:
        self.codes[phone_number] = code


def _cleanup():
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM otp_codes WHERE phone_number = ANY(:p)"), {"p": TEST_PHONES})
        # resources and availability_slots go with the user (ON DELETE CASCADE)
        conn.execute(text("DELETE FROM users WHERE phone_number = ANY(:p)"), {"p": TEST_PHONES})


@pytest.fixture
def gateway():
    return CapturingGateway()


@pytest.fixture
def client(gateway):
    app.dependency_overrides[get_sms_gateway] = lambda: gateway
    try:
        _cleanup()
    except OperationalError:
        app.dependency_overrides.clear()
        pytest.skip("Postgres not reachable (docker compose up -d)")
    yield TestClient(app)
    _cleanup()
    app.dependency_overrides.clear()


@pytest.fixture
def no_cooldown(monkeypatch):
    monkeypatch.setattr(settings, "OTP_RESEND_COOLDOWN_SECONDS", 0)


def login(client, gateway, phone):
    assert client.post(f"{API}/auth/request-otp", json={"phone_number": phone}).status_code == 200
    r = client.post(
        f"{API}/auth/verify-otp", json={"phone_number": phone, "otp": gateway.codes[phone]}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    return {"Authorization": f"Bearer {body['access_token']}"}, body["user"]["id"]


def complete_profile(client, headers, name, role):
    r = client.put(
        f"{API}/users/me",
        headers=headers,
        json={
            "name": name, "role": role, "village": "Shamirpet", "district": "Medchal",
            "lat": 17.58, "lng": 78.57,
        },
    )
    assert r.status_code == 200, r.text


@pytest.fixture
def world(client, gateway, no_cooldown):
    """A provider (OWNER) who lists things, and a farmer (VIEWER) who searches."""
    owner_h, owner_id = login(client, gateway, OWNER)
    viewer_h, viewer_id = login(client, gateway, VIEWER)
    complete_profile(client, owner_h, "Owner", "provider")
    complete_profile(client, viewer_h, "Viewer", "farmer")
    return SimpleNamespace(
        client=client, owner_h=owner_h, owner_id=owner_id, viewer_h=viewer_h, viewer_id=viewer_id,
        viewer_id_uuid=uuid.UUID(viewer_id), gateway=gateway,
    )


def make_resource(w, point, **overrides):
    body = {
        "type": "equipment", "subtype": "tractor", "description": "test", "daily_rate": 1800,
        "capacity_note": "45 HP", "lat": point[0], "lng": point[1],
    }
    body.update(overrides)
    r = w.client.post(f"{API}/resources", headers=w.owner_h, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def discover(w, centre=A, headers=None, **params):
    params = {"lat": centre[0], "lng": centre[1], **params}
    r = w.client.get(f"{API}/resources/discover", headers=headers or w.viewer_h, params=params)
    assert r.status_code == 200, r.text
    return r.json()


def ids(result):
    return [item["id"] for item in result["items"]]


def future(days):
    return (date.today() + timedelta(days=days)).isoformat()


# ---------------------------------------------------------------- creating listings

def test_create_requires_provider_role(world):
    r = world.client.post(
        f"{API}/resources", headers=world.viewer_h,
        json={"type": "equipment", "subtype": "tractor", "daily_rate": 100, "lat": 17.4, "lng": 78.4},
    )
    assert r.status_code == 403


def test_create_requires_complete_profile(world):
    headers, _ = login(world.client, world.gateway, NEWBIE)
    r = world.client.post(
        f"{API}/resources", headers=headers,
        json={"type": "equipment", "subtype": "tractor", "daily_rate": 100, "lat": 17.4, "lng": 78.4},
    )
    assert r.status_code == 403


def test_create_returns_resource_and_normalises_subtype(world):
    res = make_resource(world, A, subtype="  Seed Drill ")
    assert res["subtype"] == "seed_drill"
    assert res["lat"] == pytest.approx(A[0]) and res["lng"] == pytest.approx(A[1])
    assert res["distance_km"] is None
    assert res["owner"]["id"] == world.owner_id


def test_mine_route_is_not_swallowed_by_id_route(world):
    make_resource(world, A)
    r = world.client.get(f"{API}/resources/mine", headers=world.owner_h)
    assert r.status_code == 200 and len(r.json()) == 1


# ---------------------------------------------------------------- radius discovery

def test_listing_outside_radius_is_excluded(world):
    near = make_resource(world, A)
    far = make_resource(world, B)  # ~4.98 km away

    inside_4km = discover(world, radius_km=4)
    assert ids(inside_4km) == [near["id"]]
    assert inside_4km["total"] == 1

    inside_6km = discover(world, radius_km=6)
    assert set(ids(inside_6km)) == {near["id"], far["id"]}
    assert inside_6km["total"] == 2


def test_radius_boundary_is_inclusive(world):
    """A listing exactly `d` metres away is returned for radius d, but not for d minus a bit."""
    res = make_resource(world, B)

    with SessionLocal() as db:
        # The true distance PostGIS itself computes for this stored point and this centre
        d = db.execute(
            text("SELECT ST_Distance(location, ST_GeogFromText(:c)) FROM resources WHERE id = :id"),
            {"c": f"SRID=4326;POINT({A[1]:.10f} {A[0]:.10f})", "id": res["id"]},
        ).scalar_one()
        assert 4970 < d < 4990  # sanity: ~4.98 km

        def found(radius_m):
            items, _ = resource_service.discover(
                db, viewer_id=world.viewer_id_uuid, lat=A[0], lng=A[1], radius_m=radius_m
            )
            return [str(i.id) for i in items]

        assert res["id"] in found(d+0.001)          # exactly on the boundary: included
        assert res["id"] in found(d + 1.0)    # 1 m inside: included
        assert res["id"] not in found(d - 1.0)  # 1 m short: excluded

    # Same check through the HTTP API (radius in km), with a 1 m margin for float round-trips
    assert res["id"] in ids(discover(world, radius_km=(d + 1.0) / 1000))
    assert res["id"] not in ids(discover(world, radius_km=(d - 1.0) / 1000))


def test_results_sorted_by_distance(world):
    # Created far-first on purpose, so insertion order cannot explain the result order
    c = make_resource(world, C)
    a = make_resource(world, A)
    b = make_resource(world, B)

    result = discover(world, radius_km=15)
    assert ids(result) == [a["id"], b["id"], c["id"]]

    distances = [item["distance_km"] for item in result["items"]]
    assert distances == sorted(distances)
    assert distances[0] == pytest.approx(0.0, abs=0.01)
    assert distances[1] == pytest.approx(4.98, abs=0.05)
    assert distances[2] == pytest.approx(9.96, abs=0.1)


def test_pagination_pages_do_not_overlap(world):
    created = [make_resource(world, (A[0] + i * 0.01, LNG)) for i in range(5)]  # ~1.1 km apart
    expected = [c["id"] for c in created]  # nearest to A first

    page1 = discover(world, radius_km=20, limit=2, offset=0)
    page2 = discover(world, radius_km=20, limit=2, offset=2)
    page3 = discover(world, radius_km=20, limit=2, offset=4)

    assert [page1["total"], page2["total"], page3["total"]] == [5, 5, 5]
    assert ids(page1) + ids(page2) + ids(page3) == expected
    assert len(page3["items"]) == 1


def test_default_page_size_is_20(world):
    make_resource(world, A)
    result = discover(world, radius_km=5)
    assert result["limit"] == 20 and result["offset"] == 0


def test_filters(world):
    tractor = make_resource(world, A, daily_rate=1800)
    labor = make_resource(world, A, type="labor", subtype="sowing", daily_rate=400)

    assert ids(discover(world, radius_km=5, type="labor")) == [labor["id"]]
    assert ids(discover(world, radius_km=5, subtype="Tractor")) == [tractor["id"]]  # case-insensitive
    assert ids(discover(world, radius_km=5, max_daily_rate=500)) == [labor["id"]]


def test_own_inactive_and_non_provider_listings_are_hidden(world):
    res = make_resource(world, A)

    assert ids(discover(world, radius_km=5)) == [res["id"]]
    assert ids(discover(world, radius_km=5, headers=world.owner_h)) == []  # not my own

    # owner switches to farmer: listing hidden from discovery, but not deleted
    complete_profile(world.client, world.owner_h, "Owner", "farmer")
    assert ids(discover(world, radius_km=5)) == []
    complete_profile(world.client, world.owner_h, "Owner", "both")
    assert ids(discover(world, radius_km=5)) == [res["id"]]

    # soft delete: hidden from searches and from other users, still in /mine
    assert world.client.delete(f"{API}/resources/{res['id']}", headers=world.owner_h).status_code == 204
    assert ids(discover(world, radius_km=5)) == []
    assert world.client.get(f"{API}/resources/{res['id']}", headers=world.viewer_h).status_code == 404
    mine = world.client.get(f"{API}/resources/mine", headers=world.owner_h).json()
    assert mine[0]["is_active"] is False


def test_discover_validates_params(world):
    for params in ({"lat": 95, "lng": 78}, {"lat": 17, "lng": 78, "radius_km": 0},
                   {"lat": 17, "lng": 78, "radius_km": 500}, {"lat": 17, "lng": 78, "limit": 101}):
        r = world.client.get(f"{API}/resources/discover", headers=world.viewer_h, params=params)
        assert r.status_code == 422
    assert world.client.get(f"{API}/resources/discover", params={"lat": 17, "lng": 78}).status_code == 401


# ---------------------------------------------------------------- update / delete permissions

def test_update_put_and_patch_owner_only(world):
    res = make_resource(world, A)
    url = f"{API}/resources/{res['id']}"

    assert world.client.patch(url, headers=world.viewer_h, json={"daily_rate": 1}).status_code == 403
    assert world.client.delete(url, headers=world.viewer_h).status_code == 403

    r = world.client.put(url, headers=world.owner_h, json={"daily_rate": 2000, "lat": B[0], "lng": B[1]})
    assert r.status_code == 200
    assert r.json()["daily_rate"] == 2000 and r.json()["lat"] == pytest.approx(B[0])
    assert r.json()["subtype"] == "tractor"  # untouched

    assert world.client.patch(url, headers=world.owner_h, json={"lat": 17.0}).status_code == 422


def test_unknown_resource_is_404(world):
    fake = "00000000-0000-0000-0000-000000000000"
    assert world.client.get(f"{API}/resources/{fake}", headers=world.viewer_h).status_code == 404
    assert world.client.patch(f"{API}/resources/{fake}", headers=world.owner_h, json={}).status_code == 404


# ---------------------------------------------------------------- availability

def test_slot_lifecycle_and_booked_vs_free(world):
    res = make_resource(world, A)
    base = f"{API}/resources/{res['id']}/availability"

    r = world.client.post(base, headers=world.owner_h, json={"start_date": future(10), "end_date": future(12)})
    assert r.status_code == 201, r.text
    slot1 = r.json()
    assert slot1["is_booked"] is False

    r = world.client.post(base, headers=world.owner_h, json={"start_date": future(20), "end_date": future(21)})
    slot2 = r.json()

    # booking itself is Stage 3; simulate an accepted booking directly in the DB
    with engine.begin() as conn:
        conn.execute(text("UPDATE availability_slots SET is_booked = true WHERE id = :i"), {"i": slot1["id"]})

    everything = world.client.get(base, headers=world.viewer_h).json()
    assert [(s["id"], s["is_booked"]) for s in everything] == [(slot1["id"], True), (slot2["id"], False)]

    only_free = world.client.get(base, headers=world.viewer_h, params={"only_available": True}).json()
    assert [s["id"] for s in only_free] == [slot2["id"]]

    window = world.client.get(
        base, headers=world.viewer_h, params={"from_date": future(15), "to_date": future(30)}
    ).json()
    assert [s["id"] for s in window] == [slot2["id"]]

    # booked slot cannot be deleted, free slot can
    assert world.client.delete(f"{base}/{slot1['id']}", headers=world.owner_h).status_code == 409
    assert world.client.delete(f"{base}/{slot2['id']}", headers=world.owner_h).status_code == 204
    assert world.client.delete(f"{base}/{slot2['id']}", headers=world.owner_h).status_code == 404


def test_slot_rules(world):
    res = make_resource(world, A)
    base = f"{API}/resources/{res['id']}/availability"
    ok = {"start_date": future(10), "end_date": future(12)}

    assert world.client.post(base, headers=world.owner_h, json=ok).status_code == 201
    # overlap -> 409 from the DB exclusion constraint
    overlap = {"start_date": future(11), "end_date": future(14)}
    assert world.client.post(base, headers=world.owner_h, json=overlap).status_code == 409
    # past start -> 422; end before start -> 422
    past = {"start_date": (date.today() - timedelta(days=3)).isoformat(), "end_date": future(1)}
    assert world.client.post(base, headers=world.owner_h, json=past).status_code == 422
    backwards = {"start_date": future(9), "end_date": future(8)}
    assert world.client.post(base, headers=world.owner_h, json=backwards).status_code == 422
    # not the owner -> 403
    assert world.client.post(base, headers=world.viewer_h, json={"start_date": future(30), "end_date": future(31)}).status_code == 403


def test_available_dates_filter_in_discover(world):
    res = make_resource(world, A)
    world.client.post(
        f"{API}/resources/{res['id']}/availability", headers=world.owner_h,
        json={"start_date": future(10), "end_date": future(12)},
    )

    assert ids(discover(world, radius_km=5, available_from=future(10), available_to=future(11))) == [res["id"]]
    # range sticks out past the slot -> not covered by ONE slot
    assert ids(discover(world, radius_km=5, available_from=future(9), available_to=future(11))) == []
    assert ids(discover(world, radius_km=5, available_from=future(12), available_to=future(14))) == []

    r = world.client.get(
        f"{API}/resources/discover", headers=world.viewer_h,
        params={"lat": A[0], "lng": A[1], "available_from": future(5), "available_to": future(4)},
    )
    assert r.status_code == 422