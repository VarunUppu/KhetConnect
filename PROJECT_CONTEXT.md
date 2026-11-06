<!-- File: PROJECT_CONTEXT.md -->

# KhetConnect: Project Context

> Paste this whole file at the start of every new chatbot prompt.

## What it is

Community-based farm equipment and labor sharing platform for smallholder farmers in India.
Providers list equipment/labor with a daily rate and availability dates; farmers search nearby,
request a booking, provider accepts, they connect by phone, then rate each other.

## Tech Stack

- Backend: Python 3.11+ / FastAPI, SQLAlchemy 2.0 (sync) + psycopg2, GeoAlchemy2 + Shapely, Pydantic v2 (+ pydantic-settings), PyJWT
- Frontend: Flutter (mobile-first, Android priority). State management/HTTP client to be decided at Stage 4 (proposal: Riverpod + dio)
- DB: PostgreSQL 16 + PostGIS 3.4 (Docker image `postgis/postgis:16-3.4` for local dev)
- Auth: Phone OTP (SMS) -> JWT access token (30 days), no passwords/email
- API: REST, prefix `/api/v1`, documented in `API_CONTRACT.md` (currently v0.3); Swagger at `/docs`
- Tests: pytest + httpx (run from `backend/`: `python -m pytest -v`; DB tests auto-skip if Postgres is down)

## Local dev setup (Windows / PowerShell)

- Start the DB from the project root: `docker compose up -d db`. The app reaches it on the port in `backend/.env` (`DATABASE_URL`, currently port 5433); it must match the port published in `docker-compose.yml`.
- Activate the venv from `backend/`: `.\.venv\Scripts\Activate.ps1`.
- Run the server from `backend/` as `python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001`. Port 8000 is blocked on this machine (WinError 10013), so the dev server uses **8001**. `--reload` does not re-read `.env`; restart after editing it.
- The OTP code is printed in the uvicorn terminal (`SMS_PROVIDER=console`).
- PowerShell is not bash: `curl` is an alias for `Invoke-WebRequest`, and `VAR=value` does not work. Use `Invoke-RestMethod` (a helper `Api METHOD "/path" $token @{body}` was used for manual tests), Postman, or Swagger at `http://localhost:8001/docs`.

## Working agreement with the chatbot

- I paste files manually. Always output COMPLETE files (never diffs or "...rest unchanged"), each in its own code block with `# File: <full path>` as the first line.
- Only modify files listed under "Files Created So Far". If a new file is needed, say so and give its full path.
- Start each response with a "Files to modify" section (existing files) separate from "New files".
- Do not change the schema or API contract silently. If a change is needed, show the updated `001_init.sql`-style migration (`002_...sql`) and the updated `API_CONTRACT.md` section.
- Ask me to paste any existing file whose contents the chatbot has not seen, instead of guessing names and imports.

## Folder Structure

```text
khetconnect/
├── .gitignore
├── docker-compose.yml
├── PROJECT_CONTEXT.md
├── API_CONTRACT.md
├── backend/
│   ├── .env.example
│   ├── requirements.txt
│   ├── pytest.ini
│   ├── migrations/001_init.sql
│   ├── tests/test_auth.py  test_resources.py
│   └── app/
│       ├── main.py  config.py  db.py  deps.py
│       ├── core/errors.py
│       ├── models/      user, resource, availability_slot, booking, rating, otp_code
│       ├── schemas/     enums, common, auth, user, resource, slot, booking, rating
│       ├── routers/     auth, users, resources, slots, bookings, ratings
│       └── services/    geo, sms, otp, auth, user, resource, booking, rating
└── frontend/            (Flutter app; planned lib/core/{api,config,storage,theme,l10n}
                          and lib/features/{auth,profile,resources,bookings,ratings})
```

## Database Schema (source of truth: `backend/migrations/001_init.sql`)

All PKs are UUID (`gen_random_uuid()`). Enums are VARCHAR + CHECK. Location is `GEOGRAPHY(Point,4326)` with GiST index.

| Table              | Columns                                                                                                                                                                                                                                          |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| users              | id, phone_number (unique, E.164), name?, role (farmer/provider/both, default farmer), village?, district?, location?, language_pref (default 'hi'), trust_score numeric(3,2) default 0, rating_count int default 0, created_at                   |
| resources          | id, owner_id->users, type (equipment/labor), subtype, description?, daily_rate numeric(10,2) >= 0, capacity_note?, location (not null), is_active (default true), created_at, updated_at                                                         |
| availability_slots | id, resource_id->resources (cascade), start_date, end_date (inclusive), is_booked. EXCLUDE constraint: no overlapping slots per resource                                                                                                         |
| bookings           | id, requester_id->users, resource_id->resources, slot_id->availability_slots, status (pending/accepted/rejected/completed/cancelled), requested_at, task_description?, updated_at. Partial unique index: one accepted/completed booking per slot |
| ratings            | id, booking_id->bookings, rated_by->users, rated_user->users, score 1-5, comment?, created_at. UNIQUE(booking_id, rated_by); rated_by <> rated_user                                                                                              |
| otp_codes          | id, phone_number, code_hash, expires_at, attempts, consumed, created_at (supporting table for OTP auth)                                                                                                                                          |

## API summary (details in `API_CONTRACT.md` v0.3)

- Implemented: `GET /health`; auth (`/auth/request-otp`, `/auth/verify-otp`); users (`GET /users/me`, `PATCH|PUT /users/me`, `GET /users/{id}`); resources (`POST /resources`, `GET /resources/discover`, `GET /resources/mine`, `GET /resources/{id}`, `PATCH|PUT /resources/{id}`, `DELETE /resources/{id}`); availability (`POST|GET /resources/{id}/availability`, `DELETE /resources/{id}/availability/{slot_id}`).
- Still 501 (Stage 3): all `/bookings` endpoints, `POST /bookings/{id}/ratings`, `GET /users/{id}/ratings`.
- `GET /resources` (plain list) no longer exists; search is `GET /resources/discover`. Slot paths are `/availability`, not `/slots`.

## Conventions

- API exposes `lat`/`lng`; DB stores one `location` geography column. WKT point order is `POINT(lng lat)`. Use `services/geo_service.py` everywhere: `make_point(lat, lng)` builds a value to STORE, `geog_point(lat, lng)` builds an SQL expression to COMPARE against in queries, `lat_lng(location)` reads a stored value back.
- Radius search uses `ST_DWithin(location, point, metres)` as the filter and `ST_Distance` as the sort key (metres; API returns km, rounded to 3 decimals). Ties are broken by `id` so pagination is stable.
- Schema is managed by numbered raw SQL files in `backend/migrations/` (no Alembic yet); never use `Base.metadata.create_all`.
- Protected routes use `Depends(get_current_user)` from `app/deps.py` (401 on missing/invalid token). Endpoints that need a complete profile use `Depends(require_complete_profile)` (403).
- Literal routes (`/discover`, `/mine`) must be declared before `/{resource_id}` in the router.
- Errors are raised as `HTTPException` (`{"detail": "..."}`). Stubs still return HTTP 501 via `app/core/errors.not_implemented` (Stage 3: bookings and ratings). Implementing a stage means replacing those stubs.
- Pagination is `limit` (default 20, max 100) and `offset`; list responses are `{items, total, limit, offset}`.
- Money = JSON number (INR). Phone validation in API is India-only (+91); DB check is generic E.164.
- Settings come from `backend/.env` via `app/config.py` (`settings`); run uvicorn/pytest from `backend/`.
- Dates that mean "today" for users (e.g. slot start validation) use the Indian Standard Time date, not the server's timezone.

## Completed Stages

(Tick a stage only after its manual steps and `python -m pytest` pass.)

- [x] Stage 0: Setup & Contracts
- [x] Stage 1: Auth
- [x] Stage 2: Listings & Discovery
- [ ] Stage 3: Bookings & Ratings
- [ ] Stage 4: Flutter Skeleton & Auth
- [ ] Stage 5: Discovery/Booking Screens
- [ ] Stage 6: Integration Pass
- [ ] Stage 7: Polish
- [ ] Stage 8: Testing & Demo Prep

## Files Created So Far (update after every stage)

```text
.gitignore
docker-compose.yml
PROJECT_CONTEXT.md
API_CONTRACT.md
backend/.env.example
backend/requirements.txt
backend/pytest.ini
backend/migrations/001_init.sql
backend/tests/test_auth.py
backend/tests/test_resources.py
backend/app/__init__.py
backend/app/main.py
backend/app/config.py
backend/app/db.py
backend/app/deps.py
backend/app/core/__init__.py
backend/app/core/errors.py
backend/app/models/__init__.py
backend/app/models/user.py
backend/app/models/resource.py
backend/app/models/availability_slot.py
backend/app/models/booking.py
backend/app/models/rating.py
backend/app/models/otp_code.py
backend/app/schemas/__init__.py
backend/app/schemas/enums.py
backend/app/schemas/common.py
backend/app/schemas/auth.py
backend/app/schemas/user.py
backend/app/schemas/resource.py
backend/app/schemas/slot.py
backend/app/schemas/booking.py
backend/app/schemas/rating.py
backend/app/routers/__init__.py
backend/app/routers/auth.py
backend/app/routers/users.py
backend/app/routers/resources.py
backend/app/routers/slots.py
backend/app/routers/bookings.py
backend/app/routers/ratings.py
backend/app/services/__init__.py
backend/app/services/geo_service.py
backend/app/services/sms_service.py
backend/app/services/otp_service.py
backend/app/services/auth_service.py
backend/app/services/user_service.py
backend/app/services/resource_service.py
backend/app/services/booking_service.py
backend/app/services/rating_service.py
```

(`frontend/` files: added after `flutter create` in Stage 4.)

Stage 2 touched: `geo_service.py` (added `geog_point`), `resource_service.py` (fully implemented), `routers/resources.py`, `routers/slots.py`, `API_CONTRACT.md` (v0.3), and the new `tests/test_resources.py`. No schema changes.

## Key Decisions Made

- FastAPI over Express: best PostGIS tooling (GeoAlchemy2/Shapely), Pydantic gives validation + auto Swagger docs that mirror the contract, less boilerplate for a solo dev, Python is handy for future matching/pricing logic.
- Sync SQLAlchemy 2.0 + psycopg2 for simplicity; revisit async only if needed.
- Raw SQL migrations as source of truth; ORM models mirror them (`spatial_index=False` because the migration creates GiST indexes).
- VARCHAR + CHECK instead of Postgres ENUM types (easier to change).
- UUID primary keys.
- Single `location geography(Point,4326)` column replaces separate lat/lng.
- Added 6th table `otp_codes`; OTPs stored as HMAC-SHA256 (keyed with JWT_SECRET, bound to the phone) with 300 s expiry, 5-attempt limit, 30 s resend cooldown, single use, newest-OTP-only.
- JWT access token only (30-day expiry, claims sub/iat/exp, HS256, algorithm pinned on decode), no refresh token yet.
- Role stays a single enum `farmer|provider|both` (not a list); `both` covers dual-role users, no migration needed.
- `PUT /users/me` and `PATCH /users/me` are the same partial update; omitted/null = unchanged; phone number is not editable. `PUT /resources/{id}` is likewise an alias of `PATCH`.
- SMS is behind the `SMSGateway` interface (`services/sms_service.py`); `console` stub for dev; real providers register via `register_gateway()` and `SMS_PROVIDER`. Auth logic never changes.
- Missing token -> 401 (HTTPBearer with `auto_error=False`), not FastAPI's default 403.
- Contact reveal: the other party's phone appears in a Booking only after status is accepted/completed.
- Resources are soft-deleted (`is_active=false`); deleting an already inactive resource is idempotent (204); inactive resources are visible to their owner only.
- Explicit booking action endpoints (`/accept`, `/reject`, `/cancel`, `/complete`) instead of a generic status PATCH.
- Local Postgres via Docker Compose (PostGIS image).
- Discovery is `GET /resources/discover` (`ST_DWithin` filter, `ST_Distance` sort, id tie-break, limit/offset, `total` from a second COUNT with the same WHERE). The radius boundary is inclusive. Own listings, inactive listings and listings of owners whose role is `farmer` are excluded. Optional filters: `type`, `subtype`, `max_daily_rate`, `available_from`/`available_to` (one unbooked slot must fully cover the range).
- Slots live under `/resources/{id}/availability`; the list shows booked and free slots by default (`only_available=false`). Overlapping slots are rejected by the DB exclusion constraint (SQLSTATE 23P01 becomes 409), which is race-free.
- Subtypes are normalised to lower_snake_case on write and on filter. Slot start dates are validated against the IST date.
- Changing role to `farmer` does not delete or deactivate listings; they are hidden from discovery until the role is `provider` or `both` again.

## Known Issues / TODO

- Privacy: API currently returns exact resource lat/lng to other users (including `/resources/discover`); consider rounding to ~1 km for non-owners.
- SMS: only the console stub exists. Production needs DLT registration (sender ID + template) with the SMS provider (MSG91 assumed, not final); implement it as an `SMSGateway` subclass.
- No per-IP rate limiting on OTP endpoints yet (only per-phone cooldown/attempts).
- OTP attempt counter and cooldown are not atomic under heavy concurrency (fine for current scale).
- No cleanup job for old `otp_codes` rows.
- trust_score formula undecided (suggest Bayesian average); to be decided in Stage 3.
- Labor capacity (number of workers) is only free text in `capacity_note`.
- No photos, push notifications, payments, or chat (out of scope for now).
- Flutter: offline/low-connectivity handling and Hindi/Telugu localisation to plan in Stage 4.
- Tests: `backend/tests/test_auth.py` (Stage 1) and `backend/tests/test_resources.py` (Stage 2); DB-backed tests use real Postgres and clean up their own phone numbers.
- `test_resources.py` also deletes the manual-test accounts `+919876500001/2` (and their listings) and assumes no other listings within about 10 km of (17.385, 78.4867). Do not run it against a database with real data.
- The radius boundary test uses a 1 mm tolerance (`d + 0.001`) because `ST_Distance` and `ST_DWithin` can differ in the last float bits; the exact `d`, `d + 1 m` and `d - 1 m` semantics are asserted with margins.
- The dev server runs on port 8001 on this machine because 8000 is blocked on Windows; `API_CONTRACT.md` still names 8000 (and `10.0.2.2:8000` for the Android emulator) as the default. Revisit in Stage 4.
- No Alembic; add `002_*.sql` files by hand for schema changes.
- `db.py` and `config.py` include `uuid_pk` and `cors_origins_list`. Don't replace them with a fresh version again without checking those two names.
- Stage 2 code assumes `Booking` (in `app/models/booking.py`) has `resource_id`, `slot_id` and `status`, and that `UserPublic` supports `from_attributes`; both worked in testing.
- Tests run with `python -m pytest -v` from `backend/` (55 passing).