"""Search endpoints for unified search across services."""

import asyncio
import logging
from typing import Optional, List

from fastapi import APIRouter, Query, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.artist import Artist
from app.models.album import Album
from app.models.track import Track
from app.services.deezer import deezer_service
from app.services.ytmusic import ytmusic_service
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
    source: str  # local, deezer, ytmusic, lastfm
    in_library: bool = False
    external_ids: dict = {}


def _deezer_image_from_payload(payload: dict, kind: str) -> Optional[str]:
    """Get the best Deezer image URL from a payload."""
    if not payload:
        return None

    candidate_fields = {
        "artist": (
            "picture_xl",
            "picture_big",
            "picture_medium",
            "picture",
            "picture_small",
        ),
        "album": ("cover_xl", "cover_big", "cover_medium", "cover", "cover_small"),
    }.get(kind, ())

    for field in candidate_fields:
        value = payload.get(field)
        if value:
            return value

    md5_image = payload.get("md5_image")
    if md5_image:
        return f"https://e-cdns-images.dzcdn.net/images/{kind}/{md5_image}/1000x1000-000000-80-0-0.jpg"

    return None


class SearchResponse(BaseModel):
    """Search response containing results from multiple sources."""

    query: str
    total: int
    artists: List[SearchResultItem] = []
    albums: List[SearchResultItem] = []
    tracks: List[SearchResultItem] = []


class PreviewResponse(BaseModel):
    """Preview response for an item."""

    type: str
    name: str
    artist_name: Optional[str] = None
    image_url: Optional[str] = None
    bio: Optional[str] = None
    listeners: Optional[int] = None
    playcount: Optional[int] = None
    tags: List[str] = []
    top_albums: List[dict] = []
    tracks: List[dict] = []
    source: str = "lastfm"
    url: Optional[str] = None


async def _search_local_artists(
    db: AsyncSession, query: str, limit: int
) -> List[SearchResultItem]:
    """Search local database for artists."""
    result = await db.execute(
        select(Artist)
        .where(Artist.name.ilike(f"%{query}%"))
        .order_by(
            Artist.in_library.desc(), Artist.spotify_popularity.desc().nullslast()
        )
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
                k: v
                for k, v in {
                    "spotify_id": a.spotify_id,
                    "musicbrainz_id": a.musicbrainz_id,
                }.items()
                if v
            },
        )
        for a in artists
    ]


async def _search_local_albums(
    db: AsyncSession, query: str, limit: int, artist_filter: str = None
) -> List[SearchResultItem]:
    """Search local database for albums."""
    q = select(Album).join(Artist, Album.artist_id == Artist.id)
    conditions = [Album.title.ilike(f"%{query}%")]
    if artist_filter:
        conditions.append(Artist.name.ilike(f"%{artist_filter}%"))
        q = q.where(*conditions)
    else:
        q = q.where(Album.title.ilike(f"%{query}%"))

    q = q.order_by(
        Album.in_library.desc(), Album.spotify_popularity.desc().nullslast()
    ).limit(limit)
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
                k: v
                for k, v in {
                    "spotify_id": a.spotify_id,
                    "musicbrainz_id": a.musicbrainz_id,
                }.items()
                if v
            },
        )
        for a in albums
    ]


async def _search_local_tracks(
    db: AsyncSession, query: str, limit: int
) -> List[SearchResultItem]:
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
                k: v
                for k, v in {
                    "spotify_id": t.spotify_id,
                    "musicbrainz_id": t.musicbrainz_id,
                }.items()
                if v
            },
        )
        for t in tracks
    ]


async def _search_deezer_artists(query: str, limit: int) -> List[SearchResultItem]:
    """Search Deezer for artists."""
    try:
        results = await deezer_service.search_artists(query, limit=limit)
        return [
            SearchResultItem(
                id=f"deezer:{a['id']}",
                type="artist",
                name=a.get("name", ""),
                image_url=_deezer_image_from_payload(a, "artist"),
                source="deezer",
                in_library=False,
                external_ids={"deezer_id": str(a["id"])},
            )
            for a in results
        ]
    except Exception as e:
        logger.error(f"Deezer artist search failed: {e}")
        return []


async def _search_deezer_albums(query: str, limit: int) -> List[SearchResultItem]:
    """Search Deezer for albums."""
    try:
        results = await deezer_service.search_albums(query, limit=limit)
        return [
            SearchResultItem(
                id=f"deezer:{a['id']}",
                type="album",
                name=a.get("title", ""),
                artist_name=a.get("artist", {}).get("name"),
                image_url=_deezer_image_from_payload(a, "album")
                or _deezer_image_from_payload(a.get("artist", {}), "artist"),
                year=(
                    int(a["release_date"][:4])
                    if a.get("release_date") and len(a["release_date"]) >= 4
                    else None
                ),
                source="deezer",
                in_library=False,
                external_ids={"deezer_id": str(a["id"])},
            )
            for a in results
        ]
    except Exception as e:
        logger.error(f"Deezer album search failed: {e}")
        return []


async def _search_deezer_tracks(query: str, limit: int) -> List[SearchResultItem]:
    """Search Deezer for tracks."""
    try:
        results = await deezer_service.search_tracks(query, limit=limit)
        return [
            SearchResultItem(
                id=f"deezer:{t['id']}",
                type="track",
                name=t.get("title", ""),
                artist_name=t.get("artist", {}).get("name"),
                album_name=t.get("album", {}).get("title"),
                image_url=_deezer_image_from_payload(t.get("album", {}), "album")
                or _deezer_image_from_payload(t.get("artist", {}), "artist"),
                source="deezer",
                in_library=False,
                external_ids={
                    k: v
                    for k, v in {
                        "deezer_id": str(t["id"]),
                        "deezer_artist_id": (
                            str(t.get("artist", {}).get("id"))
                            if t.get("artist", {}).get("id")
                            else None
                        ),
                        "deezer_album_id": (
                            str(t.get("album", {}).get("id"))
                            if t.get("album", {}).get("id")
                            else None
                        ),
                    }.items()
                    if v
                },
            )
            for t in results
        ]
    except Exception as e:
        logger.error(f"Deezer track search failed: {e}")
        return []


async def _search_ytmusic_artists(query: str, limit: int) -> List[SearchResultItem]:
    """Fallback artist search via YouTube Music."""
    if not ytmusic_service.is_available:
        return []
    results = await ytmusic_service.search_artists(query, limit=limit)
    return [
        SearchResultItem(
            id=f"ytmusic:{a.get('browseId') or a.get('channelId') or a.get('artistId') or a.get('name')}",
            type="artist",
            name=a.get("artist") or a.get("name", ""),
            image_url=(
                (a.get("thumbnails") or [{}])[-1].get("url")
                if a.get("thumbnails")
                else None
            ),
            source="ytmusic",
            in_library=False,
            external_ids={
                "ytmusic_browse_id": a.get("browseId") or a.get("channelId") or ""
            },
        )
        for a in results
    ]


async def _search_ytmusic_albums(query: str, limit: int) -> List[SearchResultItem]:
    """Fallback album search via YouTube Music."""
    if not ytmusic_service.is_available:
        return []
    results = await ytmusic_service.search_albums(query, limit=limit)
    return [
        SearchResultItem(
            id=f"ytmusic:{a.get('browseId') or a.get('playlistId') or a.get('title')}",
            type="album",
            name=a.get("title", ""),
            artist_name=(
                (a.get("artists") or [{}])[0].get("name") if a.get("artists") else None
            ),
            image_url=(
                (a.get("thumbnails") or [{}])[-1].get("url")
                if a.get("thumbnails")
                else None
            ),
            source="ytmusic",
            in_library=False,
            external_ids={"ytmusic_browse_id": a.get("browseId") or ""},
        )
        for a in results
    ]


async def _search_ytmusic_tracks(query: str, limit: int) -> List[SearchResultItem]:
    """Fallback track search via YouTube Music."""
    if not ytmusic_service.is_available:
        return []
    results = await ytmusic_service.search_tracks(query, limit=limit)
    return [
        SearchResultItem(
            id=f"ytmusic:{t.get('videoId') or t.get('browseId') or t.get('title')}",
            type="track",
            name=t.get("title", ""),
            artist_name=(
                (t.get("artists") or [{}])[0].get("name")
                if t.get("artists")
                else t.get("artist")
            ),
            album_name=(
                t.get("album", {}).get("name")
                if isinstance(t.get("album"), dict)
                else None
            ),
            image_url=(
                (t.get("thumbnails") or [{}])[-1].get("url")
                if t.get("thumbnails")
                else None
            ),
            source="ytmusic",
            in_library=False,
            external_ids={"ytmusic_video_id": t.get("videoId") or ""},
        )
        for t in results
    ]


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
                image_url=a.get("image_url"),
                source="lastfm",
                in_library=False,
            )
            for a in results
        ]
    except Exception as e:
        logger.error(f"Last.fm artist search failed: {e}")
        return []


async def _search_lastfm_albums(query: str, limit: int) -> List[SearchResultItem]:
    """Search Last.fm for albums."""
    if not lastfm_service.is_available:
        return []
    try:
        results = await lastfm_service.search_albums(query, limit=limit)
        return [
            SearchResultItem(
                id=f"lastfm:{a.get('artist', 'unknown')}:{a['title']}",
                type="album",
                name=a.get("title", ""),
                artist_name=a.get("artist"),
                image_url=a.get("image_url"),
                source="lastfm",
                in_library=False,
            )
            for a in results
        ]
    except Exception as e:
        logger.error(f"Last.fm album search failed: {e}")
        return []


async def _search_lastfm_tracks(query: str, limit: int) -> List[SearchResultItem]:
    """Search Last.fm for tracks."""
    if not lastfm_service.is_available:
        return []
    try:
        results = await lastfm_service.search_tracks(query, limit=limit)
        return [
            SearchResultItem(
                id=f"lastfm:{t.get('artist', 'unknown')}:{t['title']}",
                type="track",
                name=t.get("title", ""),
                artist_name=t.get("artist"),
                image_url=t.get("image_url"),
                source="lastfm",
                in_library=False,
            )
            for t in results
        ]
    except Exception as e:
        logger.error(f"Last.fm track search failed: {e}")
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
    type: Optional[str] = Query(
        None, description="Filter by type: artist, album, track"
    ),
    source: Optional[str] = Query(
        None, description="Search specific source: local, deezer, ytmusic, lastfm"
    ),
    limit: int = Query(20, ge=1, le=100, description="Maximum results per type"),
    db: AsyncSession = Depends(get_db),
):
    """
        Search for artists, albums, and tracks across all sources.

        Results are aggregated from:
        - Local database (your library)
        - Deezer (primary)
    - YouTube Music (fallback)
        - Last.fm
    """
    artists: List[SearchResultItem] = []
    albums: List[SearchResultItem] = []
    tracks: List[SearchResultItem] = []

    search_local = source is None or source == "local"
    search_deezer = source is None or source == "deezer"
    search_ytmusic = source == "ytmusic"
    search_lastfm = source is None or source == "lastfm"

    # Run searches in parallel
    tasks = []

    if not type or type == "artist":
        if search_local:
            tasks.append(("local_artists", _search_local_artists(db, q, limit)))
        if search_deezer:
            tasks.append(("deezer_artists", _search_deezer_artists(q, limit)))
        if search_ytmusic:
            tasks.append(("ytmusic_artists", _search_ytmusic_artists(q, limit)))
        if search_lastfm:
            tasks.append(("lastfm_artists", _search_lastfm_artists(q, limit)))

    if not type or type == "album":
        if search_local:
            tasks.append(("local_albums", _search_local_albums(db, q, limit)))
        if search_deezer:
            tasks.append(("deezer_albums", _search_deezer_albums(q, limit)))
        if search_ytmusic:
            tasks.append(("ytmusic_albums", _search_ytmusic_albums(q, limit)))
        if search_lastfm:
            tasks.append(("lastfm_albums", _search_lastfm_albums(q, limit)))

    if not type or type == "track":
        if search_local:
            tasks.append(("local_tracks", _search_local_tracks(db, q, limit)))
        if search_deezer:
            tasks.append(("deezer_tracks", _search_deezer_tracks(q, limit)))
        if search_ytmusic:
            tasks.append(("ytmusic_tracks", _search_ytmusic_tracks(q, limit)))
        if search_lastfm:
            tasks.append(("lastfm_tracks", _search_lastfm_tracks(q, limit)))

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

    # Tiered fallback: only use YouTube Music if Deezer/local/Last.fm gave no results for a type.
    if source is None:
        if (not type or type == "artist") and not artists:
            artists.extend(await _search_ytmusic_artists(q, limit))
        if (not type or type == "album") and not albums:
            albums.extend(await _search_ytmusic_albums(q, limit))
        if (not type or type == "track") and not tracks:
            tracks.extend(await _search_ytmusic_tracks(q, limit))

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


@router.get("/preview", response_model=PreviewResponse)
async def get_preview(
    type: str = Query(..., description="Item type: artist, album"),
    name: str = Query(..., description="Item name (artist name or album title)"),
    artist: Optional[str] = Query(
        None, description="Artist name (required for album preview)"
    ),
    source: str = Query(
        "lastfm", description="Data source: local, deezer, ytmusic, lastfm"
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    Get preview data for a search result item.

    Returns detailed information including bio, tags, top albums/tracks,
    and listener counts for display in a preview modal.
    """
    if source == "local":
        # Preview a local artist or album
        if type == "artist":
            result = await db.execute(
                select(Artist).where(Artist.name.ilike(f"%{name}%"))
            )
            artist_obj = result.scalar_one_or_none()
            if artist_obj:
                # Get albums for this artist
                albums_result = await db.execute(
                    select(Album)
                    .where(Album.artist_id == artist_obj.id)
                    .order_by(Album.release_year.desc().nullslast())
                    .limit(6)
                )
                albums = albums_result.scalars().all()
                return PreviewResponse(
                    type="artist",
                    name=artist_obj.name,
                    image_url=artist_obj.image_url or artist_obj.thumb_url,
                    bio=artist_obj.biography,
                    listeners=artist_obj.lastfm_listeners,
                    playcount=artist_obj.lastfm_playcount,
                    tags=artist_obj.tags or [],
                    top_albums=[
                        {
                            "title": a.title,
                            "image_url": a.cover_url or a.thumb_url,
                            "release_year": a.release_year,
                        }
                        for a in albums
                    ],
                    source="local",
                )
        elif type == "album":
            result = await db.execute(
                select(Album)
                .join(Artist, Album.artist_id == Artist.id)
                .where(Album.title.ilike(f"%{name}%"))
            )
            album_obj = result.scalar_one_or_none()
            if album_obj:
                tracks_result = await db.execute(
                    select(Track)
                    .where(Track.album_id == album_obj.id)
                    .order_by(
                        Track.disc_number.asc().nullslast(),
                        Track.track_number.asc().nullslast(),
                    )
                )
                tracks = tracks_result.scalars().all()
                return PreviewResponse(
                    type="album",
                    name=album_obj.title,
                    artist_name=album_obj.artist.name if album_obj.artist else None,
                    image_url=album_obj.cover_url or album_obj.thumb_url,
                    tags=album_obj.genres or [],
                    tracks=[
                        {
                            "title": t.title,
                            "duration": t.duration_ms,
                            "track_number": t.track_number,
                        }
                        for t in tracks
                    ],
                    source="local",
                )

    if source == "deezer":
        if type == "artist":
            matches = await deezer_service.search_artists(name, limit=1)
            if matches:
                artist_data = matches[0]
                artist_id = artist_data.get("id")
                top_albums = (
                    await deezer_service.get_artist_albums(artist_id, limit=8)
                    if artist_id
                    else []
                )
                top_tracks = (
                    await deezer_service.get_artist_top_tracks(artist_id, limit=12)
                    if artist_id
                    else []
                )
                return PreviewResponse(
                    type="artist",
                    name=artist_data.get("name", name),
                    image_url=artist_data.get("picture_xl")
                    or artist_data.get("picture_big")
                    or artist_data.get("picture"),
                    tags=[],
                    top_albums=[
                        {
                            "title": album.get("title"),
                            "image_url": album.get("cover_xl")
                            or album.get("cover_big")
                            or album.get("cover"),
                            "release_year": (
                                int(album["release_date"][:4])
                                if album.get("release_date")
                                else None
                            ),
                        }
                        for album in top_albums
                    ],
                    tracks=[
                        {
                            "title": track.get("title"),
                            "duration": (track.get("duration") or 0) * 1000,
                            "track_number": track.get("track_position"),
                        }
                        for track in top_tracks
                    ],
                    source="deezer",
                    url=artist_data.get("link"),
                )
        elif type == "album":
            query = f"{artist} {name}" if artist else name
            matches = await deezer_service.search_albums(query, limit=1)
            if matches:
                album_data = matches[0]
                return PreviewResponse(
                    type="album",
                    name=album_data.get("title", name),
                    artist_name=(
                        album_data.get("artist", {}).get("name")
                        if album_data.get("artist")
                        else artist
                    ),
                    image_url=album_data.get("cover_xl")
                    or album_data.get("cover_big")
                    or album_data.get("cover"),
                    tags=[],
                    tracks=[],
                    source="deezer",
                    url=album_data.get("link"),
                )

    if source == "ytmusic":
        if type == "artist":
            matches = await ytmusic_service.search_artists(name, limit=1)
            if matches:
                first = matches[0]
                artist_name = first.get("artist") or first.get("name", name)
                return PreviewResponse(
                    type="artist",
                    name=artist_name,
                    image_url=(
                        (first.get("thumbnails") or [{}])[-1].get("url")
                        if first.get("thumbnails")
                        else None
                    ),
                    tags=[],
                    source="ytmusic",
                )
        elif type == "album":
            query = f"{artist} {name}" if artist else name
            matches = await ytmusic_service.search_albums(query, limit=1)
            if matches:
                first = matches[0]
                return PreviewResponse(
                    type="album",
                    name=first.get("title", name),
                    artist_name=(
                        (first.get("artists") or [{}])[0].get("name")
                        if first.get("artists")
                        else artist
                    ),
                    image_url=(
                        (first.get("thumbnails") or [{}])[-1].get("url")
                        if first.get("thumbnails")
                        else None
                    ),
                    tags=[],
                    source="ytmusic",
                )

    # Last.fm preview
    if type == "artist":
        data = await lastfm_service.get_artist_preview(name)
        if data:
            return PreviewResponse(
                type="artist",
                name=data["name"],
                image_url=data.get("image_url"),
                bio=data.get("bio"),
                listeners=data.get("listeners"),
                playcount=data.get("playcount"),
                tags=data.get("tags", []),
                top_albums=data.get("top_albums", []),
                source="lastfm",
                url=data.get("url"),
            )
    elif type == "album":
        artist_name = artist or ""
        data = await lastfm_service.get_album_preview(artist_name, name)
        if data:
            return PreviewResponse(
                type="album",
                name=data["title"],
                artist_name=data.get("artist"),
                image_url=data.get("image_url"),
                listeners=data.get("listeners"),
                playcount=data.get("playcount"),
                tags=data.get("tags", []),
                tracks=data.get("tracks", []),
                source="lastfm",
                url=data.get("url"),
            )

    raise HTTPException(status_code=404, detail="Preview not found")


@router.get("/artists")
async def search_artists(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Search for artists only."""
    local_results, deezer_results, ytmusic_results, lastfm_results = (
        await asyncio.gather(
            _search_local_artists(db, q, limit),
            _search_deezer_artists(q, limit),
            _search_ytmusic_artists(q, limit),
            _search_lastfm_artists(q, limit),
            return_exceptions=True,
        )
    )

    artists = []
    for result in [local_results, deezer_results, ytmusic_results, lastfm_results]:
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

    local_results, deezer_results, ytmusic_results, lastfm_results = (
        await asyncio.gather(
            _search_local_albums(db, q, limit, artist_filter=artist),
            _search_deezer_albums(search_query, limit),
            _search_ytmusic_albums(search_query, limit),
            _search_lastfm_albums(search_query, limit),
            return_exceptions=True,
        )
    )

    albums = []
    for result in [local_results, deezer_results, ytmusic_results, lastfm_results]:
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

    local_results, deezer_results, ytmusic_results, lastfm_results = (
        await asyncio.gather(
            _search_local_tracks(db, q, limit),
            _search_deezer_tracks(search_query, limit),
            _search_ytmusic_tracks(search_query, limit),
            _search_lastfm_tracks(search_query, limit),
            return_exceptions=True,
        )
    )

    tracks = []
    for result in [local_results, deezer_results, ytmusic_results, lastfm_results]:
        if isinstance(result, list):
            tracks.extend(result)

    tracks = _deduplicate_results(tracks)[:limit]
    return {"query": q, "tracks": [t.model_dump() for t in tracks]}
