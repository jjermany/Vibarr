"""Application configuration settings.

Infrastructure settings (database, redis, celery) are loaded from environment
variables. All other user-configurable settings are stored in the database and
managed through the UI.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Infrastructure settings loaded from environment variables.

    Only settings required to bootstrap the application are kept here.
    All user-configurable settings (API keys, service URLs, download
    preferences, etc.) live in the database ``app_settings`` table and
    are managed via the Settings page in the UI.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application identity
    app_name: str = "Vibarr"
    app_version: str = "0.5.0"
    debug: bool = False
    secret_key: str = "change-me-in-production"

    # Database
    database_url: str = "postgresql://vibarr:vibarr_dev@localhost:5432/vibarr"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Celery
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/1"

    @property
    def async_database_url(self) -> str:
        """Get async database URL."""
        return self.database_url.replace("postgresql://", "postgresql+asyncpg://")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
