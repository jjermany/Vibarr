"""Album endpoints."""

from typing import Optional, List
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.album import Album
from app.models.track import Track

router = APIRouter()


class AlbumResponse(BaseModel):
    """Album response model."""
    id: int
    title: str
    artist_id: int
    artist_name: Optional[str] = None
    album_type: Optional[str] = None
    release_type: Optional[str] = None
    musicbrainz_id: Optional[str] = None
    spotify_id: Optional[str] = None
    release_date: Optional[date] = None
    release_year: Optional[int] = None
    label: Optional[str] = None
    total_tracks: Optional[int] = None
    duration_ms: Optional[int] = None
    cover_url: Optional[str] = None
    thumb_url: Optional[str] = None
    genres: List[str] = []
    in_library: bool = False
    format: Optional[str] = None

    class Config:
        from_attributes = True


class AlbumDetailResponse(AlbumResponse):
    """Detailed album response with tracks and audio features."""
    description: Optional[str] = None
    avg_danceability: Optional[float] = None
    avg_energy: Optional[float] = None
    avg_valence: Optional[float] = None
    avg_tempo: Optional[float] = None
    spotify_popularity: Optional[int] = None
    lastfm_playcount: Optional[int] = None
    user_rating: Optional[float] = None
    critic_rating: Optional[float] = None
    tracks: List["TrackResponse"] = []


class TrackResponse(BaseModel):
    """Track response model."""
    id: int
    title: str
    track_number: Optional[int] = None
    disc_number: Optional[int] = None
    duration_ms: Optional[int] = None
    spotify_id: Optional[str] = None
    isrc: Optional[str] = None
    danceability: Optional[float] = None
    energy: Optional[float] = None
    valence: Optional[float] = None
    tempo: Optional[float] = None
    in_library: bool = False

    class Config:
        from_attributes = True


@router.get("", response_model=List[AlbumResponse])
async def list_albums(
    in_library: Optional[bool] = Query(None),
    artist_id: Optional[int] = Query(None),
    genre: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    decade: Optional[int] = Query(None, description="Decade start year: 1990, 2000, etc."),
    album_type: Optional[str] = Query(None),
    sort: str = Query("recent", description="Sort: recent, name, date, popularity"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List albums with optional filters."""
    query = select(Album)

    if in_library is not None:
        query = query.where(Album.in_library == in_library)

    if artist_id:
        query = query.where(Album.artist_id == artist_id)

    if genre:
        query = query.where(Album.genres.contains([genre]))

    if year:
        query = query.where(Album.release_year == year)

    if decade:
        query = query.where(Album.release_year >= decade).where(Album.release_year < decade + 10)

    if album_type:
        query = query.where(Album.album_type == album_type)

    if sort == "recent":
        query = query.order_by(Album.added_to_library_at.desc().nullslast(), Album.created_at.desc())
    elif sort == "name":
        query = query.order_by(Album.title)
    elif sort == "date":
        query = query.order_by(Album.release_date.desc().nullslast())
    elif sort == "popularity":
        query = query.order_by(Album.spotify_popularity.desc().nullslast())

    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    albums = result.scalars().all()

    return albums


@router.get("/{album_id}", response_model=AlbumDetailResponse)
async def get_album(
    album_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get album details by ID."""
    result = await db.execute(select(Album).where(Album.id == album_id))
    album = result.scalar_one_or_none()

    if not album:
        raise HTTPException(status_code=404, detail="Album not found")

    # Get tracks
    tracks_result = await db.execute(
        select(Track)
        .where(Track.album_id == album_id)
        .order_by(Track.disc_number, Track.track_number)
    )
    tracks = tracks_result.scalars().all()

    response = AlbumDetailResponse.model_validate(album)
    response.tracks = [TrackResponse.model_validate(t) for t in tracks]

    # Add artist name
    if album.artist:
        response.artist_name = album.artist.name

    return response


@router.get("/{album_id}/tracks", response_model=List[TrackResponse])
async def get_album_tracks(
    album_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get all tracks for an album."""
    result = await db.execute(
        select(Track)
        .where(Track.album_id == album_id)
        .order_by(Track.disc_number, Track.track_number)
    )
    tracks = result.scalars().all()

    return tracks


@router.post("/{album_id}/refresh")
async def refresh_album_metadata(
    album_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Refresh album metadata from external sources."""
    result = await db.execute(select(Album).where(Album.id == album_id))
    album = result.scalar_one_or_none()

    if not album:
        raise HTTPException(status_code=404, detail="Album not found")

    # TODO: Trigger Celery task to refresh metadata
    return {"status": "refresh_queued", "album_id": album_id}


@router.get("/new-releases")
async def get_new_releases(
    days: int = Query(30, ge=1, le=365, description="Number of days to look back"),
    in_library_artists: bool = Query(True, description="Only artists in library"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Get new releases from artists you follow."""
    # TODO: Implement new release detection
    return {"releases": [], "days": days}


AlbumDetailResponse.model_rebuild()
