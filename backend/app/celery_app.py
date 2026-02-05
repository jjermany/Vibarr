"""Celery application configuration."""

from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

settings = get_settings()

# Create Celery app
celery_app = Celery(
    "vibarr",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.sync",
        "app.tasks.metadata",
        "app.tasks.recommendations",
        "app.tasks.downloads",
    ],
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Task execution
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max per task
    task_soft_time_limit=3300,  # Soft limit at 55 minutes

    # Result backend
    result_expires=86400,  # Results expire after 1 day

    # Worker settings
    worker_prefetch_multiplier=1,
    worker_concurrency=4,

    # Rate limiting for external APIs
    task_annotations={
        "app.tasks.metadata.fetch_spotify_metadata": {"rate_limit": "10/m"},
        "app.tasks.metadata.fetch_lastfm_metadata": {"rate_limit": "10/m"},
        "app.tasks.metadata.fetch_musicbrainz_metadata": {"rate_limit": "1/s"},
    },

    # Scheduled tasks
    beat_schedule={
        # Sync Plex library every 6 hours
        "sync-plex-library": {
            "task": "app.tasks.sync.sync_plex_library",
            "schedule": crontab(minute=0, hour="*/6"),
        },
        # Update recommendations daily at 3 AM
        "generate-daily-recommendations": {
            "task": "app.tasks.recommendations.generate_daily_recommendations",
            "schedule": crontab(minute=0, hour=3),
        },
        # Check for new releases every 6 hours
        "check-new-releases": {
            "task": "app.tasks.recommendations.check_new_releases",
            "schedule": crontab(minute=30, hour="*/6"),
        },
        # Process wishlist searches every hour
        "process-wishlist": {
            "task": "app.tasks.downloads.process_wishlist",
            "schedule": crontab(minute=0),
        },
        # Update taste profile weekly
        "update-taste-profile": {
            "task": "app.tasks.recommendations.update_taste_profile",
            "schedule": crontab(minute=0, hour=4, day_of_week=0),  # Sunday 4 AM
        },
        # Sync listening history every 2 hours
        "sync-listening-history": {
            "task": "app.tasks.sync.sync_listening_history",
            "schedule": crontab(minute=15, hour="*/2"),
            "kwargs": {"days": 7},
        },
        # Monitor active downloads every 5 minutes
        "check-download-status": {
            "task": "app.tasks.downloads.check_download_status",
            "schedule": crontab(minute="*/5"),
        },
    },
)
