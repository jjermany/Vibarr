"""Library endpoints for Plex integration."""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.artist import Artist
from app.models.album import Album
from app.models.track import Track

router = APIRouter()


class LibraryStats(BaseModel):
    """Library statistics."""
    total_artists: int
    total_albums: int
    total_tracks: int
    total_duration_hours: float
    format_breakdown: dict
    decade_breakdown: dict
    genre_breakdown: dict


class SyncStatus(BaseModel):
    """Plex sync status."""
    is_syncing: bool
    last_sync: Optional[str] = None
    items_processed: int = 0
    items_total: int = 0
    errors: List[str] = []


@router.get("/stats", response_model=LibraryStats)
async def get_library_stats(
    db: AsyncSession = Depends(get_db),
):
    """Get library statistics."""
    # Count artists
    artist_count = await db.execute(
        select(func.count(Artist.id)).where(Artist.in_library == True)
    )

    # Count albums
    album_count = await db.execute(
        select(func.count(Album.id)).where(Album.in_library == True)
    )

    # Count tracks
    track_count = await db.execute(
        select(func.count(Track.id)).where(Track.in_library == True)
    )

    # TODO: Implement full stats calculation
    return LibraryStats(
        total_artists=artist_count.scalar() or 0,
        total_albums=album_count.scalar() or 0,
        total_tracks=track_count.scalar() or 0,
        total_duration_hours=0.0,
        format_breakdown={},
        decade_breakdown={},
        genre_breakdown={},
    )


@router.get("/artists")
async def get_library_artists(
    sort: str = Query("name", description="Sort: name, recent, plays"),
    genre: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Get artists in your library."""
    query = select(Artist).where(Artist.in_library == True)

    if genre:
        query = query.where(Artist.genres.contains([genre]))

    if sort == "name":
        query = query.order_by(Artist.sort_name or Artist.name)
    elif sort == "recent":
        query = query.order_by(Artist.updated_at.desc())
    elif sort == "plays":
        query = query.order_by(Artist.lastfm_playcount.desc().nullslast())

    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    artists = result.scalars().all()

    return {"artists": artists, "total": len(artists)}


@router.get("/albums")
async def get_library_albums(
    sort: str = Query("recent", description="Sort: recent, name, date, artist"),
    genre: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    format: Optional[str] = Query(None, description="Filter by format: flac, mp3"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Get albums in your library."""
    query = select(Album).where(Album.in_library == True)

    if genre:
        query = query.where(Album.genres.contains([genre]))

    if year:
        query = query.where(Album.release_year == year)

    if format:
        query = query.where(Album.format == format)

    if sort == "recent":
        query = query.order_by(Album.added_to_library_at.desc().nullslast())
    elif sort == "name":
        query = query.order_by(Album.title)
    elif sort == "date":
        query = query.order_by(Album.release_date.desc().nullslast())
    elif sort == "artist":
        query = query.order_by(Album.artist_id)

    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    albums = result.scalars().all()

    return {"albums": albums, "total": len(albums)}


@router.get("/recent")
async def get_recently_added(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get recently added albums."""
    result = await db.execute(
        select(Album)
        .where(Album.in_library == True)
        .order_by(Album.added_to_library_at.desc().nullslast())
        .limit(limit)
    )
    albums = result.scalars().all()

    return {"albums": albums}


@router.post("/sync")
async def sync_library(
    background_tasks: BackgroundTasks,
    full: bool = Query(False, description="Full sync vs incremental"),
):
    """Trigger Plex library sync."""
    # TODO: Implement Plex sync via Celery task
    return {
        "status": "sync_queued",
        "type": "full" if full else "incremental",
    }


@router.get("/sync/status", response_model=SyncStatus)
async def get_sync_status():
    """Get current sync status."""
    # TODO: Get actual sync status from Celery/Redis
    return SyncStatus(
        is_syncing=False,
        last_sync=None,
        items_processed=0,
        items_total=0,
        errors=[],
    )


@router.get("/genres")
async def get_library_genres(
    db: AsyncSession = Depends(get_db),
):
    """Get all genres in library with counts."""
    # TODO: Implement genre aggregation
    return {"genres": []}


@router.get("/decades")
async def get_library_decades(
    db: AsyncSession = Depends(get_db),
):
    """Get album counts by decade."""
    # TODO: Implement decade aggregation
    return {"decades": []}


@router.get("/tracks")
async def get_library_tracks(
    sort: str = Query("recent", description="Sort: recent, name, artist, album"),
    artist_id: Optional[int] = Query(None),
    album_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Get tracks in your library."""
    query = (
        select(Track)
        .join(Track.album)
        .where(Track.in_library == True)
    )

    if artist_id:
        query = query.where(Album.artist_id == artist_id)
    if album_id:
        query = query.where(Track.album_id == album_id)

    if sort == "name":
        query = query.order_by(Track.title)
    elif sort == "artist":
        query = query.order_by(Album.artist_id, Track.album_id, Track.disc_number.nullslast(), Track.track_number.nullslast())
    elif sort == "album":
        query = query.order_by(Track.album_id, Track.disc_number.nullslast(), Track.track_number.nullslast())
    else:  # recent
        query = query.order_by(Track.created_at.desc())

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    tracks = result.scalars().all()

    return {
        "tracks": [
            {
                "id": t.id,
                "title": t.title,
                "track_number": t.track_number,
                "disc_number": t.disc_number,
                "duration_ms": t.duration_ms,
                "album_id": t.album_id,
                "album_title": t.album.title if t.album else None,
                "artist_name": t.album.artist.name if t.album and t.album.artist else None,
                "cover_url": t.album.cover_url if t.album else None,
                "release_year": t.album.release_year if t.album else None,
                "in_library": t.in_library,
            }
            for t in tracks
        ],
        "total": len(tracks),
        "limit": limit,
        "offset": offset,
    }
