<!-- File: API_CONTRACT.md -->
# KhetConnect API Contract (v0.2)

Source of truth for backend and Flutter. Live Swagger UI at `http://localhost:8000/docs`
(generated from the same schemas in `backend/app/schemas/`). If this file and the
schemas disagree, fix the disagreement before writing more code.

**Implementation status:** Health, Auth and Users (except `GET /users/{id}/ratings`) are implemented (Stage 1).
Everything else returns `501` until its stage.

## Conventions

- Base URL: `/api/v1` (except `GET /health`). Android emulator reaches host at `http://10.0.2.2:8000`.
- JSON bodies, `Content-Type: application/json`.
- Auth: `Authorization: Bearer <access_token>` on every endpoint except `/auth/*` and `/health`.
- IDs are UUID strings. Dates are `YYYY-MM-DD`. Timestamps are ISO 8601 UTC.
- Money is a JSON **number**, INR per day. Distances are km. Coordinates are WGS84 `lat`, `lng` (decimal degrees).
- Phone numbers are E.164, India only for now: `+91` followed by 10 digits starting 6-9. Spaces and hyphens in input are stripped before validation.
- Pagination: `limit` (default 20, max 100) and `offset` (default 0); list responses are `{items, total, limit, offset}`.
- Errors: `{"detail": "message"}`. Validation errors (422) use FastAPI's default `{"detail": [{loc, msg, type}]}`.
- Unknown fields in request bodies are rejected with 422 where noted ("strict" bodies).

| Code | Meaning |
|------|---------|
| 400 | Business-rule failure (e.g. invalid/expired OTP) |
| 401 | Missing/invalid/expired token (response carries `WWW-Authenticate: Bearer`) |
| 403 | Authenticated but not allowed (not owner, wrong role, incomplete profile) |
| 404 | Not found |
| 409 | Conflict (slot already booked, overlapping slot, invalid status transition, duplicate rating) |
| 422 | Validation error |
| 429 | Too many requests (OTP cooldown / attempts) |
| 501 | Endpoint declared but not implemented yet |
| 502 | Upstream failure (SMS gateway could not send the OTP) |

## Shared objects

**UserPublic**
```json
{ "id": "uuid", "name": "Ramesh", "role": "farmer|provider|both",
  "village": "Shamirpet", "district": "Medchal", "trust_score": 4.5, "rating_count": 12 }
```
`role` is a single enum value; `both` means the user acts as farmer and provider. `name`, `village`, `district` are `null` until set.

**UserPrivate** = UserPublic plus
```json
{ "phone_number": "+919876543210", "lat": 17.58, "lng": 78.57,
  "language_pref": "hi", "created_at": "2026-10-05T10:00:00Z", "profile_complete": true }
```
`lat`/`lng` are `null` until a location is set. `profile_complete` is true when name, district and location are all set.

**Resource**
```json
{ "id": "uuid", "type": "equipment|labor", "subtype": "tractor",
  "description": "Mahindra 575, driver included", "daily_rate": 1800,
  "capacity_note": "45 HP", "lat": 17.6, "lng": 78.5, "is_active": true,
  "distance_km": 3.2, "created_at": "2026-10-05T10:00:00Z", "owner": { "...UserPublic" } }
```
`distance_km` is non-null only in search results. Suggested `subtype` values (free text, lower_snake_case; the app should offer these as a dropdown):
- equipment: `tractor`, `rotavator`, `plough`, `seed_drill`, `sprayer`, `harvester`, `thresher`, `water_pump`, `trolley`
- labor: `sowing`, `weeding`, `harvesting`, `spraying`, `general`

**Slot**
```json
{ "id": "uuid", "resource_id": "uuid", "start_date": "2026-10-10", "end_date": "2026-10-12", "is_booked": false }
```
Date range is inclusive on both ends.

**Booking**
```json
{ "id": "uuid", "status": "pending|accepted|rejected|completed|cancelled",
  "requested_at": "2026-10-05T10:00:00Z", "task_description": "Ploughing 2 acres",
  "resource": { "...Resource (resource.owner is the provider)" },
  "slot": { "...Slot" }, "requester": { "...UserPublic" },
  "counterparty_phone": null }
```
`counterparty_phone` is the *other* party's number and is `null` unless status is `accepted` or `completed`.

**Rating**
```json
{ "id": "uuid", "booking_id": "uuid", "rated_by": { "...UserPublic" },
  "rated_user_id": "uuid", "score": 5, "comment": "On time, fair price", "created_at": "..." }
```

## Booking state machine

```
pending  -> accepted   (owner)           sets slot.is_booked=true; other pending bookings on that slot auto-rejected
pending  -> rejected   (owner)
pending  -> cancelled  (requester)
accepted -> cancelled  (requester or owner)   frees the slot
accepted -> completed  (owner, on/after slot.start_date)
```
Any other transition returns 409.

---

## Health

### GET /health
No auth. `200 {"status": "ok", "postgis": "3.4 USE_GEOS=1 ..."}`; `503` if DB unreachable.

## Auth

Login flow: `request-otp` -> user receives a 6-digit code by SMS -> `verify-otp` -> app stores the `access_token`
and sends it as a Bearer token. There are no passwords and no refresh tokens: the access token lasts 30 days;
on `401` the app returns to the login screen.

### POST /auth/request-otp
No auth. Request: `{ "phone_number": "+919876543210" }`
Response `200`: `{ "message": "OTP sent", "expires_in_seconds": 300 }`

Rules:
- OTP is 6 digits, valid for 300 s, stored hashed (never in plain text).
- Requesting a new OTP invalidates any earlier unused one; only the newest OTP can be verified.
- Resend cooldown: 30 s per phone number, counted from the last OTP request.
- With `SMS_PROVIDER=console` the OTP is printed in the server log instead of being sent.

Errors: 422 bad number; 429 resend cooldown (message says how many seconds to wait); 502 SMS gateway failure (no OTP is created; safe to retry).

### POST /auth/verify-otp
No auth. Request: `{ "phone_number": "+919876543210", "otp": "123456" }` (`otp` must be exactly 6 digits)
Response `200`:
```json
{ "access_token": "jwt", "token_type": "bearer", "expires_in": 2592000,
  "is_new_user": true, "user": { "...UserPrivate" } }
```
Creates the user on first successful verification (`role` = `farmer`, `language_pref` = `hi`, empty profile).
An OTP can be used once. After 5 wrong attempts the OTP is locked and a new one must be requested.

Errors: 400 invalid, expired, already used, or never requested (one message for all, `"Invalid or expired OTP"`);
422 bad phone or OTP format; 429 too many attempts (the 5th wrong attempt and every attempt after it on that OTP).

**JWT claims:** `sub` (user id), `iat`, `exp`; signed HS256. Clients should treat the token as opaque.

## Users

### GET /users/me
Response `200`: UserPrivate. Errors: 401.

### PATCH /users/me   (also accepted as PUT /users/me)
`PUT` and `PATCH` behave identically (partial update): only the fields you send are changed; omitted or `null` fields are left as they are.
Request (strict body; all fields optional; `lat` and `lng` must be sent together):
```json
{ "name": "Ramesh", "role": "both", "village": "Shamirpet", "district": "Medchal",
  "lat": 17.58, "lng": 78.57, "language_pref": "te" }
```
- `name`, `village`, `district`: 1-100 characters after trimming.
- `role`: `farmer`, `provider` or `both`.
- `lat` -90..90, `lng` -180..180.
- `language_pref` is one of `hi en te ta kn mr bn gu pa ml or`.
- `phone_number` and other unknown fields are rejected (422): the phone number cannot be changed.

Response `200`: UserPrivate. Errors: 401; 422.

### GET /users/{user_id}
Response `200`: UserPublic (no phone number or location). Errors: 401; 404; 422 if not a UUID.

### GET /users/{user_id}/ratings?limit&offset
*(Stage 3: currently returns 501.)*
Response `200`: `{ "items": [Rating], "total": 0, "limit": 20, "offset": 0 }` (newest first).

## Resources

### POST /resources
Request:
```json
{ "type": "equipment", "subtype": "tractor", "description": "Mahindra 575",
  "daily_rate": 1800, "capacity_note": "45 HP", "lat": 17.6, "lng": 78.5 }
```
Response `201`: Resource. Errors: 403 if role is `farmer` or profile incomplete; 422.

### GET /resources
Query: `lat`*, `lng`* (search centre), `radius_km` (default 25, max 200), `type`, `subtype`,
`max_daily_rate`, `available_from`, `available_to` (only resources with an unbooked slot fully covering the range),
`limit`, `offset`.
Response `200`: `{ "items": [Resource with distance_km], "total": 0, "limit": 20, "offset": 0 }`
Sorted by distance ascending. Active resources only; the caller's own resources are excluded.

### GET /resources/mine
Response `200`: `[Resource]` (includes inactive).

### GET /resources/{resource_id}
Response `200`: Resource. Errors: 404.

### PATCH /resources/{resource_id}
Request (all optional): `subtype, description, daily_rate, capacity_note, lat+lng, is_active`.
Response `200`: Resource. Errors: 403 not owner; 404.

### DELETE /resources/{resource_id}
Soft delete (`is_active=false`). Response `204`. Errors: 403; 404; 409 if pending/accepted bookings exist.

## Availability slots

### POST /resources/{resource_id}/slots
Request: `{ "start_date": "2026-10-10", "end_date": "2026-10-12" }`
Response `201`: Slot. Errors: 403 not owner; 409 overlaps an existing slot; 422 end before start or start in the past.

### GET /resources/{resource_id}/slots?from_date&to_date&only_available=true
Response `200`: `[Slot]` ordered by `start_date`.

### DELETE /resources/{resource_id}/slots/{slot_id}
Response `204`. Errors: 403; 404; 409 if booked or has pending bookings.

## Bookings

### POST /bookings
Request: `{ "resource_id": "uuid", "slot_id": "uuid", "task_description": "Ploughing 2 acres" }`
Response `201`: Booking (status `pending`).
Errors: 403 booking own resource / profile incomplete; 404; 409 slot already booked; 422.

### GET /bookings?role=requester|owner&status=&limit&offset
`role=requester` (default) = bookings I made; `role=owner` = requests on my resources.
Response `200`: `{ "items": [Booking], "total": 0, "limit": 20, "offset": 0 }` (newest first).

### GET /bookings/{booking_id}
Response `200`: Booking. Visible only to requester and resource owner (else 403). 404.

### POST /bookings/{booking_id}/accept
Owner only. No body. Response `200`: Booking. 409 on invalid transition.

### POST /bookings/{booking_id}/reject
Owner only. No body. Response `200`: Booking.

### POST /bookings/{booking_id}/cancel
Requester (while pending/accepted) or owner (while accepted). No body. Response `200`: Booking.

### POST /bookings/{booking_id}/complete
Owner only, on/after slot start. No body. Response `200`: Booking.

## Ratings

### POST /bookings/{booking_id}/ratings
Request: `{ "score": 5, "comment": "On time, fair price" }` (`score` 1-5)
Response `201`: Rating. The rated user is automatically the other party.
Errors: 403 not a party to the booking; 409 booking not completed *or* already rated by you.
Side effect: recalculates the rated user's `trust_score` and `rating_count`.

## Changelog

- **v0.2 (Stage 1):** Added `PUT /users/me` as an alias of `PATCH`; omitted/`null` fields mean "unchanged"; strict body (phone number not editable);
  documented OTP rules (6 digits, 300 s, single use, newest-only, 5 attempts, 30 s cooldown); 401 for a missing token (not 403) with `WWW-Authenticate`;
  added 502 for SMS gateway failure; `role` stays a single enum (`both` covers dual roles); phone input is whitespace/hyphen-tolerant;
  `GET /users/{id}` requires auth; JWT claims documented.
- **v0.1 (Stage 0):** Initial draft.