"""Artist endpoints."""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.artist import Artist
from app.models.album import Album

router = APIRouter()


class ArtistResponse(BaseModel):
    """Artist response model."""
    id: int
    name: str
    sort_name: Optional[str] = None
    musicbrainz_id: Optional[str] = None
    spotify_id: Optional[str] = None
    image_url: Optional[str] = None
    thumb_url: Optional[str] = None
    biography: Optional[str] = None
    country: Optional[str] = None
    formed_year: Optional[int] = None
    genres: List[str] = []
    tags: List[str] = []
    in_library: bool = False
    album_count: int = 0

    class Config:
        from_attributes = True


class ArtistDetailResponse(ArtistResponse):
    """Detailed artist response with albums and stats."""
    avg_danceability: Optional[float] = None
    avg_energy: Optional[float] = None
    avg_valence: Optional[float] = None
    spotify_popularity: Optional[int] = None
    lastfm_listeners: Optional[int] = None
    lastfm_playcount: Optional[int] = None
    similar_artists: List["ArtistResponse"] = []


class SimilarArtistResponse(BaseModel):
    """Similar artist with similarity score."""
    artist: ArtistResponse
    similarity_score: float
    shared_tags: List[str] = []


@router.get("", response_model=List[ArtistResponse])
async def list_artists(
    in_library: Optional[bool] = Query(None, description="Filter by library status"),
    genre: Optional[str] = Query(None, description="Filter by genre"),
    sort: str = Query("name", description="Sort field: name, popularity, recent"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List artists with optional filters."""
    query = select(Artist)

    if in_library is not None:
        query = query.where(Artist.in_library == in_library)

    if genre:
        query = query.where(Artist.genres.contains([genre]))

    if sort == "name":
        query = query.order_by(Artist.sort_name or Artist.name)
    elif sort == "popularity":
        query = query.order_by(Artist.spotify_popularity.desc().nullslast())
    elif sort == "recent":
        query = query.order_by(Artist.created_at.desc())

    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    artists = result.scalars().all()

    return artists


@router.get("/{artist_id}", response_model=ArtistDetailResponse)
async def get_artist(
    artist_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get artist details by ID."""
    result = await db.execute(select(Artist).where(Artist.id == artist_id))
    artist = result.scalar_one_or_none()

    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")

    # Get album count
    album_count_result = await db.execute(
        select(func.count(Album.id)).where(Album.artist_id == artist_id)
    )
    album_count = album_count_result.scalar()

    response = ArtistDetailResponse.model_validate(artist)
    response.album_count = album_count

    return response


@router.get("/{artist_id}/albums", response_model=List["AlbumResponse"])
async def get_artist_albums(
    artist_id: int,
    in_library: Optional[bool] = Query(None),
    album_type: Optional[str] = Query(None, description="Filter: album, single, ep, compilation"),
    sort: str = Query("date", description="Sort: date, name, popularity"),
    db: AsyncSession = Depends(get_db),
):
    """Get all albums for an artist."""
    query = select(Album).where(Album.artist_id == artist_id)

    if in_library is not None:
        query = query.where(Album.in_library == in_library)

    if album_type:
        query = query.where(Album.album_type == album_type)

    if sort == "date":
        query = query.order_by(Album.release_date.desc().nullslast())
    elif sort == "name":
        query = query.order_by(Album.title)
    elif sort == "popularity":
        query = query.order_by(Album.spotify_popularity.desc().nullslast())

    result = await db.execute(query)
    albums = result.scalars().all()

    return albums


@router.get("/{artist_id}/similar", response_model=List[SimilarArtistResponse])
async def get_similar_artists(
    artist_id: int,
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Get similar artists based on Last.fm and audio features."""
    result = await db.execute(select(Artist).where(Artist.id == artist_id))
    artist = result.scalar_one_or_none()

    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")

    # TODO: Implement similar artist lookup via Last.fm API
    # For now, return empty list
    return []


@router.post("/{artist_id}/refresh")
async def refresh_artist_metadata(
    artist_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Refresh artist metadata from external sources."""
    result = await db.execute(select(Artist).where(Artist.id == artist_id))
    artist = result.scalar_one_or_none()

    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")

    # TODO: Trigger Celery task to refresh metadata
    return {"status": "refresh_queued", "artist_id": artist_id}


# Forward reference for type hints
from app.routers.albums import AlbumResponse
ArtistDetailResponse.model_rebuild()
