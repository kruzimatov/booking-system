from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repository root .env; a missing file is ignored (containers pass real env vars).
ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    env: Literal["dev", "test", "prod"] = "dev"
    database_url: str
    jwt_secret: SecretStr
    jwt_ttl_minutes: int = 60
    cookie_secure: bool = False

    @field_validator("jwt_secret")
    @classmethod
    def secret_is_long_enough(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters (openssl rand -hex 32)")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
