-- File: backend/migrations/001_init.sql
-- KhetConnect initial schema. Run ONCE on an empty database.
-- To reset in dev: docker compose down -v, then start and re-run.

BEGIN;

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS btree_gist;  -- needed for slot-overlap exclusion constraint

-- ---------------------------------------------------------------
-- users
-- ---------------------------------------------------------------
CREATE TABLE users (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone_number   VARCHAR(16) NOT NULL UNIQUE
                   CHECK (phone_number ~ '^\+[1-9][0-9]{7,14}$'),
    name           VARCHAR(100),
    role           VARCHAR(10) NOT NULL DEFAULT 'farmer'
                   CHECK (role IN ('farmer', 'provider', 'both')),
    village        VARCHAR(100),
    district       VARCHAR(100),
    location       GEOGRAPHY(Point, 4326),
    language_pref  VARCHAR(5) NOT NULL DEFAULT 'hi',
    trust_score    NUMERIC(3,2) NOT NULL DEFAULT 0
                   CHECK (trust_score BETWEEN 0 AND 5),
    rating_count   INTEGER NOT NULL DEFAULT 0 CHECK (rating_count >= 0),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_users_location ON users USING GIST (location);
CREATE INDEX idx_users_district ON users (district);

-- ---------------------------------------------------------------
-- resources (equipment or labor offered by a user)
-- ---------------------------------------------------------------
CREATE TABLE resources (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type           VARCHAR(10) NOT NULL CHECK (type IN ('equipment', 'labor')),
    subtype        VARCHAR(50) NOT NULL,           -- e.g. tractor, rotavator, weeding
    description    TEXT,
    daily_rate     NUMERIC(10,2) NOT NULL CHECK (daily_rate >= 0),  -- INR per day
    capacity_note  VARCHAR(200),                   -- e.g. "45 HP", "team of 4 workers"
    location       GEOGRAPHY(Point, 4326) NOT NULL,
    is_active      BOOLEAN NOT NULL DEFAULT true,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_resources_location ON resources USING GIST (location);
CREATE INDEX idx_resources_owner ON resources (owner_id);
CREATE INDEX idx_resources_type_subtype ON resources (type, subtype) WHERE is_active;

-- ---------------------------------------------------------------
-- availability_slots (inclusive date ranges)
-- ---------------------------------------------------------------
CREATE TABLE availability_slots (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_id  UUID NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
    start_date   DATE NOT NULL,
    end_date     DATE NOT NULL,
    is_booked    BOOLEAN NOT NULL DEFAULT false,
    CONSTRAINT chk_slot_dates CHECK (end_date >= start_date),
    -- a resource cannot have two overlapping slots
    CONSTRAINT excl_slot_overlap EXCLUDE USING GIST (
        resource_id WITH =,
        daterange(start_date, end_date, '[]') WITH &&
    )
);

CREATE INDEX idx_slots_resource_start ON availability_slots (resource_id, start_date)
    WHERE NOT is_booked;

-- ---------------------------------------------------------------
-- bookings
-- ---------------------------------------------------------------
CREATE TABLE bookings (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    requester_id     UUID NOT NULL REFERENCES users(id),
    resource_id      UUID NOT NULL REFERENCES resources(id),
    slot_id          UUID NOT NULL REFERENCES availability_slots(id),
    status           VARCHAR(12) NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending','accepted','rejected','completed','cancelled')),
    requested_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    task_description TEXT,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_bookings_requester ON bookings (requester_id, status);
CREATE INDEX idx_bookings_resource ON bookings (resource_id, status);
CREATE INDEX idx_bookings_slot ON bookings (slot_id);
-- at most one live (accepted/completed) booking per slot
CREATE UNIQUE INDEX uq_bookings_one_accepted_per_slot
    ON bookings (slot_id) WHERE status IN ('accepted', 'completed');

-- ---------------------------------------------------------------
-- ratings
-- ---------------------------------------------------------------
CREATE TABLE ratings (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id  UUID NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
    rated_by    UUID NOT NULL REFERENCES users(id),
    rated_user  UUID NOT NULL REFERENCES users(id),
    score       SMALLINT NOT NULL CHECK (score BETWEEN 1 AND 5),
    comment     TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_rating_once_per_rater UNIQUE (booking_id, rated_by),
    CONSTRAINT chk_no_self_rating CHECK (rated_by <> rated_user)
);

CREATE INDEX idx_ratings_rated_user ON ratings (rated_user, created_at DESC);

-- ---------------------------------------------------------------
-- otp_codes (supporting table for phone OTP auth)
-- ---------------------------------------------------------------
CREATE TABLE otp_codes (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone_number  VARCHAR(16) NOT NULL,
    code_hash     VARCHAR(128) NOT NULL,           -- never store the raw OTP
    expires_at    TIMESTAMPTZ NOT NULL,
    attempts      SMALLINT NOT NULL DEFAULT 0,
    consumed      BOOLEAN NOT NULL DEFAULT false,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_otp_phone_created ON otp_codes (phone_number, created_at DESC);

COMMIT;