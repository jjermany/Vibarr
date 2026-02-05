"""Search endpoints for unified search across services."""

import asyncio
import logging
from typing import Optional, List

from fastapi import APIRouter, Query, Depends
from pydantic import BaseModel
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.artist import Artist
from app.models.album import Album
from app.models.track import Track
from app.services.spotify import spotify_service
from app.services.lastfm import lastfm_service

logger = logging.getLogger(__name__)

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


async def _search_local_artists(db: AsyncSession, query: str, limit: int) -> List[SearchResultItem]:
    """Search local database for artists."""
    result = await db.execute(
        select(Artist)
        .where(Artist.name.ilike(f"%{query}%"))
        .order_by(Artist.in_library.desc(), Artist.spotify_popularity.desc().nullslast())
        .limit(limit)
    )
    artists = result.scalars().all()
    return [
        SearchResultItem(
            id=str(a.id),
            type="artist",
            name=a.name,
            image_url=a.image_url or a.thumb_url,
            source="local",
            in_library=a.in_library,
            external_ids={
                k: v for k, v in {
                    "spotify_id": a.spotify_id,
                    "musicbrainz_id": a.musicbrainz_id,
                }.items() if v
            },
        )
        for a in artists
    ]


async def _search_local_albums(db: AsyncSession, query: str, limit: int, artist_filter: str = None) -> List[SearchResultItem]:
    """Search local database for albums."""
    q = select(Album).join(Artist, Album.artist_id == Artist.id)
    conditions = [Album.title.ilike(f"%{query}%")]
    if artist_filter:
        conditions.append(Artist.name.ilike(f"%{artist_filter}%"))
        q = q.where(*conditions)
    else:
        q = q.where(Album.title.ilike(f"%{query}%"))

    q = q.order_by(Album.in_library.desc(), Album.spotify_popularity.desc().nullslast()).limit(limit)
    result = await db.execute(q)
    albums = result.scalars().all()
    return [
        SearchResultItem(
            id=str(a.id),
            type="album",
            name=a.title,
            artist_name=a.artist.name if a.artist else None,
            image_url=a.cover_url or a.thumb_url,
            year=a.release_year,
            source="local",
            in_library=a.in_library,
            external_ids={
                k: v for k, v in {
                    "spotify_id": a.spotify_id,
                    "musicbrainz_id": a.musicbrainz_id,
                }.items() if v
            },
        )
        for a in albums
    ]


async def _search_local_tracks(db: AsyncSession, query: str, limit: int) -> List[SearchResultItem]:
    """Search local database for tracks."""
    result = await db.execute(
        select(Track)
        .join(Album, Track.album_id == Album.id)
        .where(Track.title.ilike(f"%{query}%"))
        .order_by(Track.in_library.desc(), Track.spotify_popularity.desc().nullslast())
        .limit(limit)
    )
    tracks = result.scalars().all()
    return [
        SearchResultItem(
            id=str(t.id),
            type="track",
            name=t.title,
            artist_name=t.album.artist.name if t.album and t.album.artist else None,
            album_name=t.album.title if t.album else None,
            image_url=t.album.cover_url if t.album else None,
            source="local",
            in_library=t.in_library,
            external_ids={
                k: v for k, v in {
                    "spotify_id": t.spotify_id,
                    "musicbrainz_id": t.musicbrainz_id,
                }.items() if v
            },
        )
        for t in tracks
    ]


async def _search_spotify_artists(query: str, limit: int) -> List[SearchResultItem]:
    """Search Spotify for artists."""
    if not spotify_service.is_available:
        return []
    try:
        results = await spotify_service.search_artists(query, limit=limit)
        return [
            SearchResultItem(
                id=f"spotify:{a['id']}",
                type="artist",
                name=a.get("name", ""),
                image_url=a["images"][0]["url"] if a.get("images") else None,
                source="spotify",
                in_library=False,
                external_ids={"spotify_id": a["id"]},
            )
            for a in results
        ]
    except Exception as e:
        logger.error(f"Spotify artist search failed: {e}")
        return []


async def _search_spotify_albums(query: str, limit: int) -> List[SearchResultItem]:
    """Search Spotify for albums."""
    if not spotify_service.is_available:
        return []
    try:
        results = await spotify_service.search_albums(query, limit=limit)
        return [
            SearchResultItem(
                id=f"spotify:{a['id']}",
                type="album",
                name=a.get("name", ""),
                artist_name=a["artists"][0]["name"] if a.get("artists") else None,
                image_url=a["images"][0]["url"] if a.get("images") else None,
                year=int(a["release_date"][:4]) if a.get("release_date") else None,
                source="spotify",
                in_library=False,
                external_ids={"spotify_id": a["id"]},
            )
            for a in results
        ]
    except Exception as e:
        logger.error(f"Spotify album search failed: {e}")
        return []


async def _search_spotify_tracks(query: str, limit: int) -> List[SearchResultItem]:
    """Search Spotify for tracks."""
    if not spotify_service.is_available:
        return []
    try:
        results = await spotify_service.search_tracks(query, limit=limit)
        return [
            SearchResultItem(
                id=f"spotify:{t['id']}",
                type="track",
                name=t.get("name", ""),
                artist_name=t["artists"][0]["name"] if t.get("artists") else None,
                album_name=t["album"]["name"] if t.get("album") else None,
                image_url=t["album"]["images"][0]["url"] if t.get("album", {}).get("images") else None,
                source="spotify",
                in_library=False,
                external_ids={"spotify_id": t["id"]},
            )
            for t in results
        ]
    except Exception as e:
        logger.error(f"Spotify track search failed: {e}")
        return []


async def _search_lastfm_artists(query: str, limit: int) -> List[SearchResultItem]:
    """Search Last.fm for artists."""
    if not lastfm_service.is_available:
        return []
    try:
        results = await lastfm_service.search_artists(query, limit=limit)
        return [
            SearchResultItem(
                id=f"lastfm:{a['name']}",
                type="artist",
                name=a.get("name", ""),
                source="lastfm",
                in_library=False,
            )
            for a in results
        ]
    except Exception as e:
        logger.error(f"Last.fm artist search failed: {e}")
        return []


def _deduplicate_results(results: List[SearchResultItem]) -> List[SearchResultItem]:
    """Deduplicate search results, preferring local sources."""
    seen_names = {}
    deduped = []
    for item in results:
        key = item.name.lower().strip()
        if key in seen_names:
            existing = seen_names[key]
            # Prefer local results
            if item.source == "local" and existing.source != "local":
                deduped.remove(existing)
                deduped.append(item)
                seen_names[key] = item
        else:
            seen_names[key] = item
            deduped.append(item)
    return deduped


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
    - Last.fm
    """
    artists: List[SearchResultItem] = []
    albums: List[SearchResultItem] = []
    tracks: List[SearchResultItem] = []

    search_local = source is None or source == "local"
    search_spotify = source is None or source == "spotify"
    search_lastfm = source is None or source == "lastfm"

    # Run searches in parallel
    tasks = []

    if not type or type == "artist":
        if search_local:
            tasks.append(("local_artists", _search_local_artists(db, q, limit)))
        if search_spotify:
            tasks.append(("spotify_artists", _search_spotify_artists(q, limit)))
        if search_lastfm:
            tasks.append(("lastfm_artists", _search_lastfm_artists(q, limit)))

    if not type or type == "album":
        if search_local:
            tasks.append(("local_albums", _search_local_albums(db, q, limit)))
        if search_spotify:
            tasks.append(("spotify_albums", _search_spotify_albums(q, limit)))

    if not type or type == "track":
        if search_local:
            tasks.append(("local_tracks", _search_local_tracks(db, q, limit)))
        if search_spotify:
            tasks.append(("spotify_tracks", _search_spotify_tracks(q, limit)))

    # Execute all searches concurrently
    task_names = [t[0] for t in tasks]
    task_coros = [t[1] for t in tasks]
    results = await asyncio.gather(*task_coros, return_exceptions=True)

    for name, result in zip(task_names, results):
        if isinstance(result, Exception):
            logger.error(f"Search task {name} failed: {result}")
            continue

        if "artists" in name:
            artists.extend(result)
        elif "albums" in name:
            albums.extend(result)
        elif "tracks" in name:
            tracks.extend(result)

    # Deduplicate
    artists = _deduplicate_results(artists)[:limit]
    albums = _deduplicate_results(albums)[:limit]
    tracks = _deduplicate_results(tracks)[:limit]

    total = len(artists) + len(albums) + len(tracks)

    return SearchResponse(
        query=q,
        total=total,
        artists=artists,
        albums=albums,
        tracks=tracks,
    )


@router.get("/artists")
async def search_artists(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Search for artists only."""
    local_results, spotify_results, lastfm_results = await asyncio.gather(
        _search_local_artists(db, q, limit),
        _search_spotify_artists(q, limit),
        _search_lastfm_artists(q, limit),
        return_exceptions=True,
    )

    artists = []
    for result in [local_results, spotify_results, lastfm_results]:
        if isinstance(result, list):
            artists.extend(result)

    artists = _deduplicate_results(artists)[:limit]
    return {"query": q, "artists": [a.model_dump() for a in artists]}


@router.get("/albums")
async def search_albums(
    q: str = Query(..., min_length=1),
    artist: Optional[str] = Query(None, description="Filter by artist name"),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Search for albums only."""
    search_query = f"{artist} {q}" if artist else q

    local_results, spotify_results = await asyncio.gather(
        _search_local_albums(db, q, limit, artist_filter=artist),
        _search_spotify_albums(search_query, limit),
        return_exceptions=True,
    )

    albums = []
    for result in [local_results, spotify_results]:
        if isinstance(result, list):
            albums.extend(result)

    albums = _deduplicate_results(albums)[:limit]
    return {"query": q, "albums": [a.model_dump() for a in albums]}


@router.get("/tracks")
async def search_tracks(
    q: str = Query(..., min_length=1),
    artist: Optional[str] = Query(None),
    album: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Search for tracks only."""
    search_parts = [q]
    if artist:
        search_parts.append(artist)
    if album:
        search_parts.append(album)
    search_query = " ".join(search_parts)

    local_results, spotify_results = await asyncio.gather(
        _search_local_tracks(db, q, limit),
        _search_spotify_tracks(search_query, limit),
        return_exceptions=True,
    )

    tracks = []
    for result in [local_results, spotify_results]:
        if isinstance(result, list):
            tracks.extend(result)

    tracks = _deduplicate_results(tracks)[:limit]
    return {"query": q, "tracks": [t.model_dump() for t in tracks]}
