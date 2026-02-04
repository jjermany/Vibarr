"""Plex library sync tasks."""

import logging
from datetime import datetime

from app.celery_app import celery_app
from app.database import AsyncSessionLocal
from app.services.plex import plex_service
from app.models.artist import Artist
from app.models.album import Album

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="app.tasks.sync.sync_plex_library")
def sync_plex_library(self, full_sync: bool = False):
    """
    Sync music library from Plex.

    Args:
        full_sync: If True, sync all items. If False, only sync changes.
    """
    import asyncio
    return asyncio.get_event_loop().run_until_complete(
        _sync_plex_library_async(self, full_sync)
    )


async def _sync_plex_library_async(task, full_sync: bool):
    """Async implementation of Plex sync."""
    logger.info(f"Starting Plex library sync (full={full_sync})")

    if not plex_service.is_available:
        logger.error("Plex service not available")
        return {"status": "error", "message": "Plex service not available"}

    try:
        # Get all artists from Plex
        plex_artists = await plex_service.get_all_artists()
        total = len(plex_artists)
        processed = 0
        created_artists = 0
        created_albums = 0
        updated = 0

        async with AsyncSessionLocal() as db:
            for plex_artist in plex_artists:
                try:
                    # Update task progress
                    processed += 1
                    task.update_state(
                        state="PROGRESS",
                        meta={
                            "current": processed,
                            "total": total,
                            "status": f"Processing {plex_artist['name']}",
                        },
                    )

                    # Check if artist exists
                    from sqlalchemy import select
                    result = await db.execute(
                        select(Artist).where(
                            Artist.plex_rating_key == plex_artist["rating_key"]
                        )
                    )
                    artist = result.scalar_one_or_none()

                    if artist:
                        # Update existing artist
                        artist.name = plex_artist["name"]
                        artist.sort_name = plex_artist.get("sort_name")
                        artist.image_url = plex_artist.get("thumb")
                        artist.genres = plex_artist.get("genres", [])
                        artist.in_library = True
                        artist.updated_at = datetime.utcnow()
                        updated += 1
                    else:
                        # Create new artist
                        artist = Artist(
                            name=plex_artist["name"],
                            sort_name=plex_artist.get("sort_name"),
                            image_url=plex_artist.get("thumb"),
                            genres=plex_artist.get("genres", []),
                            in_library=True,
                            plex_rating_key=plex_artist["rating_key"],
                        )
                        db.add(artist)
                        created_artists += 1

                    await db.flush()

                    # Sync albums for this artist
                    plex_albums = await plex_service.get_artist_albums(
                        plex_artist["rating_key"]
                    )

                    for plex_album in plex_albums:
                        album_result = await db.execute(
                            select(Album).where(
                                Album.plex_rating_key == plex_album["rating_key"]
                            )
                        )
                        album = album_result.scalar_one_or_none()

                        if album:
                            album.title = plex_album["title"]
                            album.release_year = plex_album.get("year")
                            album.cover_url = plex_album.get("thumb")
                            album.genres = plex_album.get("genres", [])
                            album.in_library = True
                            album.updated_at = datetime.utcnow()
                        else:
                            album = Album(
                                title=plex_album["title"],
                                artist_id=artist.id,
                                release_year=plex_album.get("year"),
                                cover_url=plex_album.get("thumb"),
                                genres=plex_album.get("genres", []),
                                in_library=True,
                                plex_rating_key=plex_album["rating_key"],
                                added_to_library_at=datetime.fromisoformat(
                                    plex_album["added_at"]
                                ) if plex_album.get("added_at") else datetime.utcnow(),
                            )
                            db.add(album)
                            created_albums += 1

                    await db.commit()

                except Exception as e:
                    logger.error(f"Error syncing artist {plex_artist.get('name')}: {e}")
                    await db.rollback()
                    continue

        result = {
            "status": "completed",
            "total_artists": total,
            "created_artists": created_artists,
            "created_albums": created_albums,
            "updated": updated,
        }
        logger.info(f"Plex sync completed: {result}")
        return result

    except Exception as e:
        logger.error(f"Plex sync failed: {e}")
        return {"status": "error", "message": str(e)}


@celery_app.task(name="app.tasks.sync.sync_listening_history")
def sync_listening_history(days: int = 7):
    """Sync listening history from Plex."""
    import asyncio
    return asyncio.get_event_loop().run_until_complete(
        _sync_listening_history_async(days)
    )


async def _sync_listening_history_async(days: int):
    """Async implementation of listening history sync."""
    from datetime import timedelta
    from app.models.listening_history import ListeningHistory

    logger.info(f"Syncing listening history for past {days} days")

    if not plex_service.is_available:
        return {"status": "error", "message": "Plex service not available"}

    try:
        since = datetime.utcnow() - timedelta(days=days)
        history = await plex_service.get_listening_history(since=since)

        created = 0
        async with AsyncSessionLocal() as db:
            for item in history:
                track_data = item.get("track", {})
                played_at = item.get("played_at")

                if not played_at:
                    continue

                played_at_dt = datetime.fromisoformat(played_at.replace("Z", "+00:00"))

                # Check if already recorded
                from sqlalchemy import select
                existing = await db.execute(
                    select(ListeningHistory).where(
                        ListeningHistory.plex_track_key == track_data.get("rating_key"),
                        ListeningHistory.played_at == played_at_dt,
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                # Create new history entry
                entry = ListeningHistory(
                    plex_track_key=track_data.get("rating_key"),
                    plex_album_key=track_data.get("album_rating_key"),
                    played_at=played_at_dt,
                    duration_ms=track_data.get("duration_ms"),
                    track_duration_ms=track_data.get("duration_ms"),
                    completion_percentage=100.0,  # Plex only records completed plays
                    source="plex",
                    hour_of_day=played_at_dt.hour,
                    day_of_week=played_at_dt.weekday(),
                )
                db.add(entry)
                created += 1

            await db.commit()

        return {"status": "completed", "entries_created": created}

    except Exception as e:
        logger.error(f"Listening history sync failed: {e}")
        return {"status": "error", "message": str(e)}
