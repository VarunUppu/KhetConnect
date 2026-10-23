# File: backend/app/config.py
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_SECRET = "dev-only-secret-change-me-0123456789"


class Settings(BaseSettings):
    # .env is read from the current working directory: run uvicorn/pytest from backend/
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "KhetConnect"
    APP_ENV: str = "development"

    DATABASE_URL: str = "postgresql+psycopg2://khet:khet@localhost:5432/khetconnect"

    # Comma-separated list of allowed origins, e.g. "http://localhost:3000,http://localhost:8080"
    CORS_ORIGINS: str = "*"

    JWT_SECRET: str = _DEV_SECRET
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_DAYS: int = 30

    OTP_TTL_SECONDS: int = 300
    OTP_RESEND_COOLDOWN_SECONDS: int = 30
    OTP_MAX_ATTEMPTS: int = 5

    SMS_PROVIDER: str = "console"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @model_validator(mode="after")
    def _reject_default_secret_in_production(self) -> "Settings":
        if self.APP_ENV == "production" and self.JWT_SECRET == _DEV_SECRET:
            raise ValueError("JWT_SECRET must be set to a real secret when APP_ENV=production")
        return self


settings = Settings()