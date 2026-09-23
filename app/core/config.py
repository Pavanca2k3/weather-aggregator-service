from functools import lru_cache

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, overridable via environment variables or .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "nokia"
    version: str = "0.1.0"
    debug: bool = False
    cors_origins: list[str] = ["*"]

    # PostgreSQL. Port 5434 is deliberate: tentoro occupies 5432/5433.
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5434
    postgres_user: str = "nokia_app"
    postgres_password: str = ""
    postgres_db: str = "nokia"

    echo_sql: bool = False

    # Outbound HTTP to Open-Meteo. The cache TTL matches Open-Meteo's own
    # ~15 minute refresh cadence; see adapters/outbound/openmeteo/session.py.
    # Endpoints are settings so a test (or a staging run) can point the service
    # at a stub without patching anything inside it.
    openmeteo_forecast_url: str = "https://api.open-meteo.com/v1/forecast"
    openmeteo_geocoding_url: str = "https://geocoding-api.open-meteo.com/v1/search"

    http_cache_enabled: bool = True
    http_cache_path: str = ".cache"
    http_cache_ttl_seconds: int = 900
    http_retries: int = 3
    http_backoff_factor: float = 0.3

    @computed_field
    @property
    def database_url(self) -> str:
        """Async driver URL used by the app and Alembic."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
