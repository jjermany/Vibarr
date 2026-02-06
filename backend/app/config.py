"""Application configuration settings."""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "Vibarr"
    app_version: str = "0.1.0"
    debug: bool = False
    secret_key: str = "change-me-in-production"

    # Database
    database_url: str = "postgresql://vibarr:vibarr_dev@localhost:5432/vibarr"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Celery
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/1"

    # Spotify API
    spotify_client_id: Optional[str] = None
    spotify_client_secret: Optional[str] = None

    # Last.fm API
    lastfm_api_key: Optional[str] = None
    lastfm_shared_secret: Optional[str] = None

    # Plex
    plex_url: Optional[str] = None
    plex_token: Optional[str] = None

    # Prowlarr
    prowlarr_url: Optional[str] = None
    prowlarr_api_key: Optional[str] = None

    # MusicBrainz
    musicbrainz_user_agent: str = "Vibarr/1.0 (https://github.com/jjermany/Vibarr)"

    # TheAudioDB (free tier)
    audiodb_api_key: str = "2"  # Free tier key

    # Recommendation settings
    recommendation_refresh_hours: int = 24
    new_release_check_hours: int = 6
    max_recommendations_per_request: int = 50

    # Download settings
    auto_download_enabled: bool = False
    auto_download_confidence_threshold: float = 0.8
    preferred_quality: str = "flac"  # flac, 320, v0
    max_concurrent_downloads: int = 3
    download_path: str = "/downloads"
    completed_download_path: str = "/downloads/completed"

    # qBittorrent
    qbittorrent_url: Optional[str] = None
    qbittorrent_username: str = "admin"
    qbittorrent_password: str = ""
    qbittorrent_category: str = "vibarr"

    # Beets
    beets_enabled: bool = False
    beets_config_path: str = "/config/beets/config.yaml"
    beets_library_path: str = "/music"
    beets_auto_import: bool = True
    beets_move_files: bool = True  # Move vs copy after import

    @property
    def async_database_url(self) -> str:
        """Get async database URL."""
        return self.database_url.replace("postgresql://", "postgresql+asyncpg://")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
