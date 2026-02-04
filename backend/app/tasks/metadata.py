"""Metadata fetching tasks."""

import logging
from datetime import datetime

from app.celery_app import celery_app
from app.database import AsyncSessionLocal
from app.services.spotify import spotify_service
from app.services.lastfm import lastfm_service
from app.services.musicbrainz import musicbrainz_service
from app.services.audiodb import audiodb_service
from app.models.artist import Artist
from app.models.album import Album

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.metadata.fetch_artist_metadata")
def fetch_artist_metadata(artist_id: int):
    """Fetch metadata for an artist from all sources."""
    import asyncio
    return asyncio.get_event_loop().run_until_complete(
        _fetch_artist_metadata_async(artist_id)
    )


async def _fetch_artist_metadata_async(artist_id: int):
    """Async implementation of artist metadata fetch."""
    logger.info(f"Fetching metadata for artist {artist_id}")

    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        result = await db.execute(select(Artist).where(Artist.id == artist_id))
        artist = result.scalar_one_or_none()

        if not artist:
            return {"status": "error", "message": "Artist not found"}

        # Fetch from multiple sources
        updates = {}

        # MusicBrainz (primary source)
        if artist.musicbrainz_id:
            mb_data = await musicbrainz_service.get_artist(artist.musicbrainz_id)
            if mb_data:
                updates.update({
                    "sort_name": mb_data.get("sort_name"),
                    "disambiguation": mb_data.get("disambiguation"),
                    "country": mb_data.get("country"),
                    "tags": mb_data.get("tags", []),
                })
        else:
            # Search MusicBrainz
            mb_results = await musicbrainz_service.search_artists(artist.name, limit=1)
            if mb_results:
                best_match = mb_results[0]
                updates["musicbrainz_id"] = best_match.get("id")

        # Spotify
        if spotify_service.is_available:
            if artist.spotify_id:
                spotify_data = await spotify_service.get_artist(artist.spotify_id)
            else:
                spotify_results = await spotify_service.search_artists(artist.name, limit=1)
                if spotify_results:
                    spotify_data = spotify_results[0]
                    updates["spotify_id"] = spotify_data.get("id")
                else:
                    spotify_data = None

            if spotify_data:
                updates.update({
                    "spotify_popularity": spotify_data.get("popularity"),
                    "genres": spotify_data.get("genres", []) or updates.get("tags", []),
                })
                images = spotify_data.get("images", [])
                if images:
                    updates["image_url"] = images[0].get("url")
                    if len(images) > 1:
                        updates["thumb_url"] = images[-1].get("url")

        # Last.fm
        if lastfm_service.is_available:
            lastfm_data = await lastfm_service.get_artist_info(artist.name)
            if lastfm_data:
                updates.update({
                    "lastfm_url": lastfm_data.get("url"),
                    "lastfm_listeners": lastfm_data.get("listeners"),
                    "lastfm_playcount": lastfm_data.get("playcount"),
                    "biography": lastfm_data.get("bio") or updates.get("biography"),
                })
                if not updates.get("tags"):
                    updates["tags"] = lastfm_data.get("tags", [])

        # TheAudioDB
        audiodb_data = await audiodb_service.search_artist(artist.name)
        if audiodb_data:
            if not updates.get("biography"):
                updates["biography"] = audiodb_data.get("biography")
            updates["formed_year"] = audiodb_data.get("formed_year")
            updates["disbanded_year"] = audiodb_data.get("disbanded_year")

            # Get images
            images = audiodb_data.get("images", {})
            if images.get("thumb") and not updates.get("image_url"):
                updates["image_url"] = images["thumb"]
            if images.get("banner"):
                updates["banner_url"] = images["banner"]

        # Apply updates
        for key, value in updates.items():
            if value is not None:
                setattr(artist, key, value)

        artist.metadata_updated_at = datetime.utcnow()
        await db.commit()

        return {
            "status": "completed",
            "artist_id": artist_id,
            "updates_applied": list(updates.keys()),
        }


@celery_app.task(name="app.tasks.metadata.fetch_album_metadata")
def fetch_album_metadata(album_id: int):
    """Fetch metadata for an album from all sources."""
    import asyncio
    return asyncio.get_event_loop().run_until_complete(
        _fetch_album_metadata_async(album_id)
    )


async def _fetch_album_metadata_async(album_id: int):
    """Async implementation of album metadata fetch."""
    logger.info(f"Fetching metadata for album {album_id}")

    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        result = await db.execute(
            select(Album).where(Album.id == album_id)
        )
        album = result.scalar_one_or_none()

        if not album:
            return {"status": "error", "message": "Album not found"}

        # Get artist name
        artist_result = await db.execute(
            select(Artist).where(Artist.id == album.artist_id)
        )
        artist = artist_result.scalar_one_or_none()
        artist_name = artist.name if artist else ""

        updates = {}

        # MusicBrainz
        if album.musicbrainz_id:
            mb_data = await musicbrainz_service.get_release_group(album.musicbrainz_id)
            if mb_data:
                updates.update({
                    "tags": mb_data.get("tags", []),
                    "album_type": mb_data.get("primary_type", "").lower(),
                })
        else:
            mb_results = await musicbrainz_service.search_release_groups(
                album.title, artist=artist_name, limit=1
            )
            if mb_results:
                best_match = mb_results[0]
                updates["musicbrainz_id"] = best_match.get("id")
                updates["musicbrainz_release_group_id"] = best_match.get("id")
                updates["album_type"] = best_match.get("primary_type", "").lower()
                if best_match.get("first_release_date"):
                    try:
                        from datetime import date
                        date_str = best_match["first_release_date"]
                        if len(date_str) == 4:
                            updates["release_year"] = int(date_str)
                        else:
                            updates["release_date"] = date.fromisoformat(date_str[:10])
                            updates["release_year"] = updates["release_date"].year
                    except (ValueError, TypeError):
                        pass

        # Spotify
        if spotify_service.is_available:
            if album.spotify_id:
                spotify_data = await spotify_service.get_album(album.spotify_id)
            else:
                spotify_results = await spotify_service.search_albums(
                    f"{artist_name} {album.title}", limit=1
                )
                if spotify_results:
                    spotify_data = spotify_results[0]
                    updates["spotify_id"] = spotify_data.get("id")
                else:
                    spotify_data = None

            if spotify_data:
                updates["spotify_popularity"] = spotify_data.get("popularity")
                updates["total_tracks"] = spotify_data.get("total_tracks")
                updates["label"] = spotify_data.get("label")

                images = spotify_data.get("images", [])
                if images:
                    updates["cover_url"] = images[0].get("url")
                    if len(images) > 1:
                        updates["thumb_url"] = images[-1].get("url")

                # Fetch audio features for tracks
                if spotify_data.get("id"):
                    tracks = await spotify_service.get_album_tracks(spotify_data["id"])
                    track_ids = [t.get("id") for t in tracks if t.get("id")]
                    if track_ids:
                        features = await spotify_service.get_audio_features(track_ids)
                        if features:
                            # Calculate averages
                            avg_features = _calculate_avg_features(features)
                            updates.update(avg_features)

        # Last.fm
        if lastfm_service.is_available:
            lastfm_data = await lastfm_service.get_album_info(artist_name, album.title)
            if lastfm_data:
                updates["lastfm_playcount"] = lastfm_data.get("playcount")
                if not updates.get("tags"):
                    updates["tags"] = lastfm_data.get("tags", [])

        # TheAudioDB
        audiodb_data = await audiodb_service.search_album(artist_name, album.title)
        if audiodb_data:
            if not updates.get("description"):
                updates["description"] = audiodb_data.get("description")
            if audiodb_data.get("score"):
                updates["critic_rating"] = audiodb_data["score"]

            images = audiodb_data.get("images", {})
            if images.get("thumb") and not updates.get("cover_url"):
                updates["cover_url"] = images["thumb"]

        # Apply updates
        for key, value in updates.items():
            if value is not None:
                setattr(album, key, value)

        album.metadata_updated_at = datetime.utcnow()
        await db.commit()

        return {
            "status": "completed",
            "album_id": album_id,
            "updates_applied": list(updates.keys()),
        }


def _calculate_avg_features(features: list) -> dict:
    """Calculate average audio features."""
    if not features:
        return {}

    keys = [
        "danceability",
        "energy",
        "valence",
        "tempo",
        "acousticness",
        "instrumentalness",
    ]

    averages = {}
    for key in keys:
        values = [f.get(key) for f in features if f.get(key) is not None]
        if values:
            averages[f"avg_{key}"] = sum(values) / len(values)

    return averages


@celery_app.task(name="app.tasks.metadata.fetch_spotify_metadata")
def fetch_spotify_metadata(item_type: str, item_id: int):
    """Fetch Spotify-specific metadata (rate limited)."""
    if item_type == "artist":
        return fetch_artist_metadata.delay(item_id)
    elif item_type == "album":
        return fetch_album_metadata.delay(item_id)
    return {"status": "error", "message": "Invalid item type"}


@celery_app.task(name="app.tasks.metadata.fetch_lastfm_metadata")
def fetch_lastfm_metadata(item_type: str, item_id: int):
    """Fetch Last.fm-specific metadata (rate limited)."""
    if item_type == "artist":
        return fetch_artist_metadata.delay(item_id)
    elif item_type == "album":
        return fetch_album_metadata.delay(item_id)
    return {"status": "error", "message": "Invalid item type"}


@celery_app.task(name="app.tasks.metadata.fetch_musicbrainz_metadata")
def fetch_musicbrainz_metadata(item_type: str, item_id: int):
    """Fetch MusicBrainz-specific metadata (rate limited to 1/s)."""
    if item_type == "artist":
        return fetch_artist_metadata.delay(item_id)
    elif item_type == "album":
        return fetch_album_metadata.delay(item_id)
    return {"status": "error", "message": "Invalid item type"}


@celery_app.task(name="app.tasks.metadata.bulk_fetch_metadata")
def bulk_fetch_metadata(artist_ids: list = None, album_ids: list = None):
    """Queue metadata fetch for multiple items."""
    queued = 0

    if artist_ids:
        for artist_id in artist_ids:
            fetch_artist_metadata.delay(artist_id)
            queued += 1

    if album_ids:
        for album_id in album_ids:
            fetch_album_metadata.delay(album_id)
            queued += 1

    return {"status": "queued", "tasks_queued": queued}
