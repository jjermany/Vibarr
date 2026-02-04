"""Search endpoints for unified search across services."""

from typing import Optional, List
from fastapi import APIRouter, Query, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter()


class SearchResultItem(BaseModel):
    """Individual search result."""
    id: str
    type: str  # artist, album, track
    name: str
    artist_name: Optional[str] = None
    album_name: Optional[str] = None
    image_url: Optional[str] = None
    year: Optional[int] = None
    source: str  # local, spotify, musicbrainz, lastfm
    in_library: bool = False
    external_ids: dict = {}


class SearchResponse(BaseModel):
    """Search response containing results from multiple sources."""
    query: str
    total: int
    artists: List[SearchResultItem] = []
    albums: List[SearchResultItem] = []
    tracks: List[SearchResultItem] = []


@router.get("", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=1, description="Search query"),
    type: Optional[str] = Query(None, description="Filter by type: artist, album, track"),
    source: Optional[str] = Query(None, description="Search specific source: local, spotify, musicbrainz"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results per type"),
    db: AsyncSession = Depends(get_db),
):
    """
    Search for artists, albums, and tracks across all sources.

    Results are aggregated from:
    - Local database (your library)
    - Spotify
    - MusicBrainz
    - Last.fm
    """
    results = SearchResponse(query=q, total=0)

    # TODO: Implement actual search logic across services
    # For now, return empty results

    return results


@router.get("/artists")
async def search_artists(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Search for artists only."""
    # TODO: Implement
    return {"query": q, "artists": []}


@router.get("/albums")
async def search_albums(
    q: str = Query(..., min_length=1),
    artist: Optional[str] = Query(None, description="Filter by artist name"),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Search for albums only."""
    # TODO: Implement
    return {"query": q, "albums": []}


@router.get("/tracks")
async def search_tracks(
    q: str = Query(..., min_length=1),
    artist: Optional[str] = Query(None),
    album: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Search for tracks only."""
    # TODO: Implement
    return {"query": q, "tracks": []}
