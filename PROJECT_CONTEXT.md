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
- API: REST, prefix `/api/v1`, documented in `API_CONTRACT.md`; Swagger at `/docs`
- Tests: pytest + httpx (run from `backend/`: `python -m pytest -v`; DB tests auto-skip if Postgres is down)

## Working agreement with the chatbot

- I paste files manually. Always output COMPLETE files (never diffs or "...rest unchanged"), each in its own code block with `# File: <full path>` as the first line.
- Only modify files listed under "Files Created So Far". If a new file is needed, say so and give its full path.
- Start each response with a "Files to modify" section (existing files) separate from "New files".
- Do not change the schema or API contract silently. If a change is needed, show the updated `001_init.sql`-style migration (`002_...sql`) and the updated `API_CONTRACT.md` section.

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
│   ├── tests/test_auth.py
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

## Conventions

- API exposes `lat`/`lng`; DB stores one `location` geography column. WKT point order is `POINT(lng lat)`. Use `services/geo_service.py` (`make_point(lat, lng)`, `lat_lng(location)`) everywhere.
- Radius search uses `ST_DWithin(location, point::geography, metres)` and `ST_Distance` (metres; API returns km).
- Schema is managed by numbered raw SQL files in `backend/migrations/` (no Alembic yet); never use `Base.metadata.create_all`.
- Protected routes use `Depends(get_current_user)` from `app/deps.py` (401 on missing/invalid token). Endpoints that need a complete profile use `Depends(require_complete_profile)` (403).
- Stubs still return HTTP 501 (Stage 2+). Implementing a stage means replacing those stubs.
- Money = JSON number (INR). Phone validation in API is India-only (+91); DB check is generic E.164.
- Settings come from `backend/.env` via `app/config.py` (`settings`); run uvicorn/pytest from `backend/`.

## Completed Stages

(Tick Stage 0 only after commands 1-9 in the setup list pass. Tick Stage 1 only after the manual curl steps and `python -m pytest` pass.)

- [x] Stage 0: Setup & Contracts
- [x] Stage 1: Auth (code written; awaiting manual verification)
- [ ] Stage 2: Listings & Discovery
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
- `PUT /users/me` and `PATCH /users/me` are the same partial update; omitted/null = unchanged; phone number is not editable.
- SMS is behind the `SMSGateway` interface (`services/sms_service.py`); `console` stub for dev; real providers register via `register_gateway()` and `SMS_PROVIDER`. Auth logic never changes.
- Missing token -> 401 (HTTPBearer with `auto_error=False`), not FastAPI's default 403.
- Contact reveal: the other party's phone appears in a Booking only after status is accepted/completed.
- Resources are soft-deleted (`is_active=false`).
- Explicit booking action endpoints (`/accept`, `/reject`, `/cancel`, `/complete`) instead of a generic status PATCH.
- Local Postgres via Docker Compose (PostGIS image).

## Known Issues / TODO

- Privacy: API currently returns exact resource lat/lng to other users; consider rounding to ~1 km for non-owners.
- SMS: only the console stub exists. Production needs DLT registration (sender ID + template) with the SMS provider (MSG91 assumed, not final); implement it as an `SMSGateway` subclass.
- No per-IP rate limiting on OTP endpoints yet (only per-phone cooldown/attempts).
- OTP attempt counter and cooldown are not atomic under heavy concurrency (fine for current scale).
- Changing role to `farmer` does not yet deactivate existing resources (decide in Stage 2).
- No cleanup job for old `otp_codes` rows.
- trust_score formula undecided (suggest Bayesian average).
- Labor capacity (number of workers) is only free text in `capacity_note`.
- No photos, push notifications, payments, or chat (out of scope for now).
- Flutter: offline/low-connectivity handling and Hindi/Telugu localisation to plan in Stage 4.
- Tests: `backend/tests/test_auth.py` covers Stage 1 only; DB-backed tests use real Postgres and clean up phones +919000000001/2.
- No Alembic; add `002_*.sql` files by hand for schema changes.
- Stage 1 files db.py and config.py were rebuilt without the originals, so they now include uuid_pk and cors_origins_list. Don't replace them with a fresh version again without checking those two names.
- Tests run with python -m pytest -v from backend/ (38 passing).