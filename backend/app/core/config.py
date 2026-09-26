from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repository root .env; a missing file is ignored (containers pass real env vars).
ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    database_url: str
    jwt_secret: SecretStr
    jwt_ttl_minutes: int = 60
    cookie_secure: bool = False
    business_timezone: str = "Asia/Tashkent"
    min_notice_minutes: int = Field(default=60, ge=0)
    max_advance_days: int = Field(default=60, ge=1)
    max_active_bookings_per_client: int = Field(default=5, ge=1)
    cancel_cutoff_minutes: int = Field(default=120, ge=0)
    currency: str = "UZS"

    @field_validator("business_timezone")
    @classmethod
    def timezone_exists(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"Unknown timezone: {value}") from exc
        return value

    @property
    def business_tz(self) -> ZoneInfo:
        return ZoneInfo(self.business_timezone)

    @field_validator("jwt_secret")
    @classmethod
    def secret_is_long_enough(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters (openssl rand -hex 32)")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
