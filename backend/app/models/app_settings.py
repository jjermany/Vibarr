"""Database-backed application settings model."""

from sqlalchemy import Column, Integer, String, Text, DateTime, func
from app.database import Base


class AppSettings(Base):
    """Key-value store for application settings.

    All user-configurable settings are stored here instead of environment
    variables, so they can be managed from the UI.
    """

    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(255), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=True)
    category = Column(String(100), nullable=False, default="general")
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


# Default settings seeded on first run
DEFAULT_APP_SETTINGS = [
    # Spotify API
    {"key": "spotify_client_id", "value": "", "category": "spotify"},
    {"key": "spotify_client_secret", "value": "", "category": "spotify"},
    # Last.fm API
    {"key": "lastfm_api_key", "value": "", "category": "lastfm"},
    {"key": "lastfm_shared_secret", "value": "", "category": "lastfm"},
    # Plex
    {"key": "plex_url", "value": "", "category": "plex"},
    {"key": "plex_token", "value": "", "category": "plex"},
    # Prowlarr
    {"key": "prowlarr_url", "value": "", "category": "prowlarr"},
    {"key": "prowlarr_api_key", "value": "", "category": "prowlarr"},
    # MusicBrainz
    {"key": "musicbrainz_user_agent", "value": "Vibarr/1.0 (https://github.com/jjermany/Vibarr)", "category": "musicbrainz"},
    # TheAudioDB
    {"key": "audiodb_api_key", "value": "2", "category": "audiodb"},
    # Download settings
    {"key": "auto_download_enabled", "value": "false", "category": "downloads"},
    {"key": "auto_download_confidence_threshold", "value": "0.8", "category": "downloads"},
    {"key": "preferred_quality", "value": "flac", "category": "downloads"},
    {"key": "max_concurrent_downloads", "value": "3", "category": "downloads"},
    {"key": "download_path", "value": "/downloads", "category": "downloads"},
    {"key": "completed_download_path", "value": "/downloads/completed", "category": "downloads"},
    # qBittorrent
    {"key": "qbittorrent_url", "value": "", "category": "qbittorrent"},
    {"key": "qbittorrent_username", "value": "admin", "category": "qbittorrent"},
    {"key": "qbittorrent_password", "value": "", "category": "qbittorrent"},
    {"key": "qbittorrent_category", "value": "vibarr", "category": "qbittorrent"},
    {"key": "qbittorrent_categories", "value": "vibarr,music", "category": "qbittorrent"},
    {"key": "qbittorrent_incomplete_path", "value": "", "category": "qbittorrent"},
    {"key": "qbittorrent_completed_path", "value": "", "category": "qbittorrent"},
    {"key": "qbittorrent_remove_completed", "value": "false", "category": "qbittorrent"},
    # Beets
    {"key": "beets_enabled", "value": "false", "category": "beets"},
    {"key": "beets_config_path", "value": "/config/beets/config.yaml", "category": "beets"},
    {"key": "beets_library_path", "value": "/music", "category": "beets"},
    {"key": "beets_auto_import", "value": "true", "category": "beets"},
    {"key": "beets_move_files", "value": "true", "category": "beets"},
    # Recommendation settings
    {"key": "recommendation_refresh_hours", "value": "24", "category": "general"},
    {"key": "new_release_check_hours", "value": "6", "category": "general"},
    {"key": "max_recommendations_per_request", "value": "50", "category": "general"},
    # Multi-user settings
    {"key": "registration_enabled", "value": "true", "category": "general"},
    {"key": "max_users", "value": "10", "category": "general"},
    # ML Taste Profiling
    {"key": "ml_profiling_enabled", "value": "true", "category": "general"},
    {"key": "taste_embedding_half_life_days", "value": "21.0", "category": "general"},
]
