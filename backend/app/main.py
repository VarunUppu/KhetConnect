# File: backend/app/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.db import engine
from app.routers import auth, bookings, ratings, resources, slots, users

app = FastAPI(
    title="KhetConnect API",
    version="0.1.0",
    description="Community farm equipment & labor sharing for smallholder farmers.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = "/api/v1"
for r in (
    auth.router,
    users.router,
    resources.router,
    slots.router,
    bookings.router,
    ratings.router,
):
    app.include_router(r, prefix=API_PREFIX)


@app.get("/health", tags=["health"])
def health():
    """Checks the API is up, the DB is reachable, and PostGIS is installed."""
    try:
        with engine.connect() as conn:
            postgis = conn.execute(text("SELECT PostGIS_Version()")).scalar()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Database check failed: {exc}")
    return {"status": "ok", "postgis": postgis}