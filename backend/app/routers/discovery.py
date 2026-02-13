"""Discovery endpoints for new music exploration."""

import logging
from typing import Optional, List, Dict, Any
from collections import Counter

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.artist import Artist
from app.models.album import Album
from app.models.track import Track
from app.models.recommendation import Recommendation
from app.models.listening_history import ListeningHistory
from app.services.lastfm import lastfm_service
from app.services.deezer import deezer_service
from app.services.auth import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()


def _tokenize(text: str) -> List[str]:
    return [t for t in (text or '').lower().replace('&', ' ').replace('-', ' ').split() if t]


def _contains_any_token(text: str, tokens: List[str]) -> bool:
    haystack = (text or '').lower()
    return any(token in haystack for token in tokens if len(token) > 2)


def _preferred_genre_match(value: str, genre: str) -> bool:
    return (value or "").strip().lower() == (genre or "").strip().lower()




def _normalized_language(value: Optional[str]) -> Optional[str]:
    normalized = (value or "").strip().lower()
    return normalized or None


def _get_user_languages(current_user: Optional[User]) -> List[str]:
    if not current_user:
        return []
    langs: List[str] = []
    for candidate in [current_user.preferred_language, *(current_user.secondary_languages or [])]:
        normalized = _normalized_language(candidate)
        if normalized and normalized not in langs:
            langs.append(normalized)
    return langs


def _extract_language_metadata(track: Dict[str, Any]) -> Optional[str]:
    for source in [track, track.get("album") or {}, track.get("artist") or {}]:
        for key in ("language", "lang", "lyrics_language", "spoken_language"):
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip().lower()
    return None


def _language_match(language_metadata: str, preferred_languages: List[str]) -> bool:
    for preferred in preferred_languages:
        if language_metadata == preferred or language_metadata.startswith(f"{preferred}-"):
            return True
    return False


def _build_language_filter_summary(
    preferred_languages: List[str],
    broaden_language: bool,
    filtered_count: int,
    no_metadata_count: int,
) -> Dict[str, Any]:
    enabled = bool(preferred_languages) and not broaden_language
    if not preferred_languages:
        note = "Language filtering is off because no preferred profile language is set."
    elif broaden_language:
        note = "Language filtering is broadened; all matches are shown regardless of metadata language."
    else:
        note = (
            "Language filtering is applied when provider metadata includes language. "
            "Items without language metadata are kept as a conservative fallback."
        )
    return {
        "enabled": enabled,
        "broadened": broaden_language,
        "preferred_languages": preferred_languages,
        "filtered_count": filtered_count,
        "fallback_without_metadata": no_metadata_count,
        "note": note,
    }


def _deezer_cover(album: Dict[str, Any]) -> Optional[str]:
    return (
        album.get('cover_xl')
        or album.get('cover_big')
        or album.get('cover_medium')
        or album.get('cover')
        or album.get('cover_small')
    )


class DiscoveryPlaylist(BaseModel):
    """A discovery playlist (like Discover Weekly)."""

    id: str
    name: str
    description: str
    cover_url: Optional[str] = None
    track_count: int
    generated_at: str
    expires_at: Optional[str] = None


class DiscoveryItem(BaseModel):
    """Item in a discovery feed."""

    id: str
    type: str  # artist, album, playlist
    title: str
    subtitle: Optional[str] = None
    image_url: Optional[str] = None
    reason: Optional[str] = None
    confidence: float = 0.0


@router.get("/home")
async def get_discovery_home(
    db: AsyncSession = Depends(get_db),
):
    """
    Get personalized discovery home feed.

    Returns curated sections built from actual recommendations:
    - Release Radar (new releases from library artists)
    - Because you listened to X (similar artist recs)
    - Deep Cuts (lesser-known albums from known artists)
    - Genre Spotlight
    """
    from datetime import datetime

    sections = []

    # 1. Release Radar - new releases from library artists
    release_recs = await db.execute(
        select(Recommendation)
        .where(Recommendation.category == "release_radar")
        .where(Recommendation.dismissed == False)
        .where(Recommendation.expires_at > datetime.utcnow())
        .order_by(Recommendation.confidence_score.desc())
        .limit(20)
    )
    release_items = release_recs.scalars().all()
    release_section_items = []
    for rec in release_items:
        item = {
            "id": rec.id,
            "recommendation_id": rec.id,
            "type": rec.recommendation_type,
            "reason": rec.reason,
            "confidence": rec.confidence_score,
        }
        if rec.artist_id:
            artist = await db.execute(select(Artist).where(Artist.id == rec.artist_id))
            artist = artist.scalar_one_or_none()
            if artist:
                item["artist_name"] = artist.name
                item["image_url"] = artist.image_url
                item["in_library"] = artist.in_library
        if rec.album_id:
            album = await db.execute(select(Album).where(Album.id == rec.album_id))
            album = album.scalar_one_or_none()
            if album:
                item["title"] = album.title
                item["image_url"] = album.cover_url or item.get("image_url")
                item["in_library"] = album.in_library
        release_section_items.append(item)

    sections.append(
        {
            "id": "release_radar",
            "title": "Release Radar",
            "description": "New releases from artists you follow",
            "type": "album_list",
            "items": release_section_items,
        }
    )

    # 2. Similar artists - "Because You Listened To..."
    similar_recs = await db.execute(
        select(Recommendation)
        .where(Recommendation.category == "similar_artists")
        .where(Recommendation.dismissed == False)
        .where(Recommendation.expires_at > datetime.utcnow())
        .order_by(Recommendation.confidence_score.desc())
        .limit(20)
    )
    similar_items = similar_recs.scalars().all()
    similar_section_items = []
    for rec in similar_items:
        item = {
            "id": rec.id,
            "recommendation_id": rec.id,
            "type": "artist",
            "reason": rec.reason,
            "confidence": rec.confidence_score,
        }
        if rec.artist_id:
            artist = await db.execute(select(Artist).where(Artist.id == rec.artist_id))
            artist = artist.scalar_one_or_none()
            if artist:
                item["name"] = artist.name
                item["image_url"] = artist.image_url
                item["genres"] = artist.genres or []
                item["in_library"] = artist.in_library
        similar_section_items.append(item)

    sections.append(
        {
            "id": "similar_to_recent",
            "title": "Because You Listened To...",
            "description": "Artists similar to your recent plays",
            "type": "artist_list",
            "items": similar_section_items,
        }
    )

    # 3. Deep Cuts
    deep_recs = await db.execute(
        select(Recommendation)
        .where(Recommendation.category == "deep_cuts")
        .where(Recommendation.dismissed == False)
        .where(Recommendation.expires_at > datetime.utcnow())
        .order_by(Recommendation.confidence_score.desc())
        .limit(20)
    )
    deep_items = deep_recs.scalars().all()
    deep_section_items = []
    for rec in deep_items:
        item = {
            "id": rec.id,
            "recommendation_id": rec.id,
            "type": "album",
            "reason": rec.reason,
            "confidence": rec.confidence_score,
        }
        if rec.album_id:
            album = await db.execute(select(Album).where(Album.id == rec.album_id))
            album = album.scalar_one_or_none()
            if album:
                item["title"] = album.title
                item["image_url"] = album.cover_url
                item["in_library"] = album.in_library
                if album.artist:
                    item["artist_name"] = album.artist.name
        elif rec.artist_id:
            artist = await db.execute(select(Artist).where(Artist.id == rec.artist_id))
            artist = artist.scalar_one_or_none()
            if artist:
                item["artist_name"] = artist.name
                item["image_url"] = artist.image_url
                item["in_library"] = artist.in_library
        deep_section_items.append(item)

    sections.append(
        {
            "id": "deep_cuts",
            "title": "Deep Cuts",
            "description": "Hidden gems from artists you know",
            "type": "album_list",
            "items": deep_section_items,
        }
    )

    # 4. Genre Spotlight - based on top genres in library
    genre_result = await db.execute(
        select(Artist.genres)
        .where(Artist.in_library == True)
        .where(Artist.genres.isnot(None))
    )
    all_genres = []
    for row in genre_result:
        if row[0]:
            all_genres.extend(row[0])

    genre_counts = Counter(all_genres)
    top_genre = genre_counts.most_common(1)[0][0] if genre_counts else None

    genre_items = []
    if top_genre:
        genre_artists = await db.execute(
            select(Artist)
            .where(Artist.in_library == False)
            .where(Artist.genres.isnot(None))
            .order_by(Artist.spotify_popularity.desc().nullslast())
            .limit(50)
        )
        for artist in genre_artists.scalars().all():
            if artist.genres and top_genre in artist.genres:
                genre_items.append(
                    {
                        "id": artist.id,
                        "type": "artist",
                        "name": artist.name,
                        "image_url": artist.image_url,
                        "genres": artist.genres or [],
                        "in_library": artist.in_library,
                    }
                )
                if len(genre_items) >= 10:
                    break

    sections.append(
        {
            "id": "genre_spotlight",
            "title": f"Genre Spotlight: {top_genre.title() if top_genre else 'Explore'}",
            "description": f"Explore {top_genre if top_genre else 'new genres'}",
            "type": "artist_list",
            "items": genre_items,
        }
    )

    # 5. Discover Weekly placeholder
    discover_recs = await db.execute(
        select(Recommendation)
        .where(Recommendation.category.in_(["genre_explore", "mood_based"]))
        .where(Recommendation.dismissed == False)
        .where(Recommendation.expires_at > datetime.utcnow())
        .order_by(Recommendation.confidence_score.desc())
        .limit(15)
    )
    discover_items = discover_recs.scalars().all()
    discover_section_items = []
    for rec in discover_items:
        item = {
            "id": rec.id,
            "recommendation_id": rec.id,
            "type": rec.recommendation_type,
            "reason": rec.reason,
            "confidence": rec.confidence_score,
        }
        if rec.artist_id:
            artist = await db.execute(select(Artist).where(Artist.id == rec.artist_id))
            artist = artist.scalar_one_or_none()
            if artist:
                item["name"] = artist.name
                item["image_url"] = artist.image_url
                item["in_library"] = artist.in_library
        discover_section_items.append(item)

    sections.insert(
        0,
        {
            "id": "discover_weekly",
            "title": "Discover Weekly",
            "description": "Fresh picks based on your taste",
            "type": "artist_list",
            "items": discover_section_items,
        },
    )

    return {"sections": sections}


@router.get("/playlists")
async def get_discovery_playlists(
    db: AsyncSession = Depends(get_db),
):
    """Get all generated discovery playlists."""
    from datetime import datetime

    # Count recommendations by category
    categories = {
        "discover_weekly": {
            "categories": ["genre_explore", "mood_based", "similar_artists"],
            "name": "Discover Weekly",
            "description": "Your weekly mix of fresh music",
        },
        "release_radar": {
            "categories": ["release_radar"],
            "name": "Release Radar",
            "description": "New music from artists you follow",
        },
        "deep_cuts": {
            "categories": ["deep_cuts"],
            "name": "Deep Cuts",
            "description": "Hidden gems from artists you know",
        },
    }

    playlists = []
    for playlist_id, info in categories.items():
        count_result = await db.execute(
            select(func.count(Recommendation.id))
            .where(Recommendation.category.in_(info["categories"]))
            .where(Recommendation.dismissed == False)
            .where(Recommendation.expires_at > datetime.utcnow())
        )
        count = count_result.scalar() or 0

        playlists.append(
            DiscoveryPlaylist(
                id=playlist_id,
                name=info["name"],
                description=info["description"],
                track_count=count,
                generated_at=datetime.utcnow().isoformat(),
            )
        )

    return {"playlists": playlists}


@router.get("/similar/{artist_id}")
async def get_similar_discoveries(
    artist_id: int,
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Get discovery suggestions based on a specific artist."""
    # Get the base artist
    artist = await db.execute(select(Artist).where(Artist.id == artist_id))
    artist = artist.scalar_one_or_none()
    if not artist:
        return {"based_on_artist_id": artist_id, "artists": [], "albums": []}

    similar_artists = []
    similar_albums = []

    # Try Last.fm for similar artists
    if lastfm_service.is_available:
        try:
            similar = await lastfm_service.get_similar_artists(artist.name, limit=limit)
            for s in similar:
                # Check if in our DB
                db_result = await db.execute(
                    select(Artist).where(func.lower(Artist.name) == s["name"].lower())
                )
                db_artist = db_result.scalar_one_or_none()

                similar_artists.append(
                    {
                        "name": s.get("name"),
                        "match": s.get("match", 0),
                        "id": db_artist.id if db_artist else None,
                        "image_url": db_artist.image_url if db_artist else None,
                        "in_library": db_artist.in_library if db_artist else False,
                        "genres": db_artist.genres if db_artist else [],
                    }
                )
        except Exception as e:
            logger.error(f"Error getting similar artists for {artist.name}: {e}")

    # Get recommendations already generated for this artist
    recs = await db.execute(
        select(Recommendation)
        .where(Recommendation.based_on_artist_id == artist_id)
        .where(Recommendation.dismissed == False)
        .order_by(Recommendation.confidence_score.desc())
        .limit(limit)
    )
    for rec in recs.scalars().all():
        if rec.recommendation_type == "album" and rec.album_id:
            album = await db.execute(select(Album).where(Album.id == rec.album_id))
            album = album.scalar_one_or_none()
            if album:
                similar_albums.append(
                    {
                        "id": album.id,
                        "title": album.title,
                        "cover_url": album.cover_url,
                        "artist_name": album.artist.name if album.artist else "",
                        "reason": rec.reason,
                    }
                )

    return {
        "based_on_artist_id": artist_id,
        "based_on_artist_name": artist.name,
        "artists": similar_artists,
        "albums": similar_albums,
    }


@router.get("/genre/{genre}")
async def explore_genre(
    genre: str,
    sort: str = Query("popular", description="Sort: popular, recent, random"),
    limit: int = Query(50, ge=1, le=200),
    broaden_language: bool = Query(False, description="Disable language filtering to broaden discovery"),
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Explore a specific genre with local + Deezer results."""
    artist_query = select(Artist).where(Artist.genres.isnot(None))

    if sort == "popular":
        artist_query = artist_query.order_by(Artist.lastfm_listeners.desc().nullslast())
    elif sort == "recent":
        artist_query = artist_query.order_by(Artist.created_at.desc())
    else:
        artist_query = artist_query.order_by(func.random())

    artist_query = artist_query.limit(200)
    result = await db.execute(artist_query)

    artists = []
    albums = []
    for a in result.scalars().all():
        if a.genres and genre.lower() in [g.lower() for g in a.genres]:
            artists.append(
                {
                    "id": a.id,
                    "name": a.name,
                    "image_url": a.image_url or a.thumb_url,
                    "genres": a.genres,
                    "in_library": a.in_library,
                    "popularity": a.lastfm_listeners,
                    "source": "local",
                }
            )
            if len(artists) >= limit:
                break

    artist_ids = [a["id"] for a in artists[:20]]
    if artist_ids:
        album_result = await db.execute(
            select(Album)
            .where(Album.artist_id.in_(artist_ids))
            .order_by(Album.release_year.desc().nullslast(), Album.created_at.desc())
            .limit(limit)
        )
        for album in album_result.scalars().all():
            albums.append(
                {
                    "id": album.id,
                    "title": album.title,
                    "artist_name": album.artist.name if album.artist else "",
                    "cover_url": album.cover_url or album.thumb_url,
                    "release_year": album.release_year,
                    "in_library": album.in_library,
                    "source": "local",
                }
            )

    preferred_languages = _get_user_languages(current_user)
    language_filtered_count = 0
    language_fallback_count = 0
    deezer_tracks: List[Dict[str, Any]] = []
    deezer_genres = await deezer_service.get_genres()
    deezer_genre = next(
        (g for g in deezer_genres if _preferred_genre_match(g.get("name", ""), genre)),
        None,
    )

    if deezer_genre and deezer_genre.get("id") is not None:
        deezer_artists = await deezer_service.get_genre_artists(
            deezer_genre["id"], limit=max(40, min(limit * 2, 120))
        )
        for artist in deezer_artists:
            if not artist.get("id"):
                continue

            artist_top_tracks = await deezer_service.get_artist_top_tracks(
                artist["id"], limit=2
            )
            if preferred_languages and not broaden_language:
                has_language_match = any(
                    (
                        (metadata_language := _extract_language_metadata(track))
                        and _language_match(metadata_language, preferred_languages)
                    )
                    for track in artist_top_tracks
                )
                if not has_language_match:
                    language_filtered_count += 1
                    continue

            if not any(str(a.get("id")) == f"deezer:{artist['id']}" for a in artists):
                artists.append(
                    {
                        "id": f"deezer:{artist['id']}",
                        "name": artist.get("name", ""),
                        "image_url": artist.get("picture_xl")
                        or artist.get("picture_big")
                        or artist.get("picture"),
                        "genres": [genre],
                        "in_library": False,
                        "popularity": artist.get("nb_fan"),
                        "source": "deezer",
                    }
                )

            deezer_tracks.extend(artist_top_tracks)
            if len(artists) >= limit or len(deezer_tracks) >= max(60, min(limit * 3, 180)):
                break
    else:
        deezer_tracks = await deezer_service.search_tracks(
            f'genre:"{genre}"', limit=max(40, min(limit * 3, 150))
        )

    genre_tokens = _tokenize(genre)
    for track in deezer_tracks:
        artist = track.get("artist") or {}
        album = track.get("album") or {}
        title_blob = " ".join(
            [
                track.get("title", ""),
                artist.get("name", ""),
                album.get("title", ""),
            ]
        )
        if genre_tokens and not _contains_any_token(title_blob, genre_tokens):
            continue

        metadata_language = _extract_language_metadata(track)
        if metadata_language:
            if preferred_languages and not broaden_language and not _language_match(metadata_language, preferred_languages):
                language_filtered_count += 1
                continue
        else:
            if preferred_languages and not broaden_language:
                language_filtered_count += 1
                continue
            language_fallback_count += 1

        if artist.get("id") and not any(
            str(a.get("id")) == f"deezer:{artist['id']}" for a in artists
        ):
            artists.append(
                {
                    "id": f"deezer:{artist['id']}",
                    "name": artist.get("name", ""),
                    "image_url": artist.get("picture_xl")
                    or artist.get("picture_big")
                    or artist.get("picture"),
                    "genres": [genre],
                    "in_library": False,
                    "popularity": track.get("rank"),
                    "source": "deezer",
                }
            )

        if album.get("id") and not any(
            str(a.get("id")) == f"deezer:{album['id']}" for a in albums
        ):
            albums.append(
                {
                    "id": f"deezer:{album['id']}",
                    "title": album.get("title", ""),
                    "artist_name": artist.get("name", ""),
                    "cover_url": _deezer_cover(album),
                    "release_year": (
                        int(album.get("release_date", "")[:4])
                        if album.get("release_date")
                        else None
                    ),
                    "in_library": False,
                    "source": "deezer",
                }
            )

        if len(artists) >= limit and len(albums) >= limit:
            break

    all_genres = Counter()
    for a in artists:
        for g in a.get("genres", []):
            if g and g.lower() != genre.lower():
                all_genres[g] += 1
    related_genres = [g for g, _ in all_genres.most_common(10)]

    return {
        "genre": genre,
        "artists": artists[:limit],
        "albums": albums[:limit],
        "related_genres": related_genres,
        "language_filter": _build_language_filter_summary(
            preferred_languages=preferred_languages,
            broaden_language=broaden_language,
            filtered_count=language_filtered_count,
            no_metadata_count=language_fallback_count,
        ),
    }


@router.get("/decade/{decade}")
async def explore_decade(
    decade: int,
    genre: Optional[str] = Query(
        default=None,
        description="Optional genre filter applied to decade exploration results.",
    ),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Time machine - explore a specific decade with local + Deezer results."""
    decade_start = decade
    decade_end = decade + 9

    album_query = (
        select(Album)
        .where(Album.release_year >= decade_start)
        .where(Album.release_year <= decade_end)
    )

    if genre:
        album_query = album_query.where(Album.genres.isnot(None))

    album_query = album_query.order_by(
        Album.release_year.desc().nullslast(), Album.created_at.desc()
    ).limit(200)

    result = await db.execute(album_query)
    albums_data = result.scalars().all()

    albums = []
    artists_seen = set()
    for album in albums_data:
        if (
            genre
            and album.genres
            and genre.lower() not in [g.lower() for g in album.genres]
        ):
            continue

        item = {
            "id": album.id,
            "title": album.title,
            "artist_name": album.artist.name if album.artist else "",
            "cover_url": album.cover_url or album.thumb_url,
            "release_year": album.release_year,
            "in_library": album.in_library,
            "source": "local",
        }
        albums.append(item)

        if album.artist and album.artist.id not in artists_seen:
            artists_seen.add(album.artist.id)

        if len(albums) >= limit:
            break

    deezer_tracks = await deezer_service.search_tracks(
        f"year:{decade_start}-{decade_end}", limit=max(40, min(limit * 3, 150))
    )
    for track in deezer_tracks:
        album = track.get("album") or {}
        artist = track.get("artist") or {}
        release = album.get("release_date") or ""
        year = int(release[:4]) if len(release) >= 4 and release[:4].isdigit() else None
        if year is not None and not (decade_start <= year <= decade_end):
            continue
        if album.get("id") and not any(
            str(a.get("id")) == f"deezer:{album['id']}" for a in albums
        ):
            albums.append(
                {
                    "id": f"deezer:{album['id']}",
                    "title": album.get("title", ""),
                    "artist_name": artist.get("name", ""),
                    "cover_url": _deezer_cover(album),
                    "release_year": year,
                    "in_library": False,
                    "source": "deezer",
                }
            )
        if len(albums) >= limit:
            break

    highlights = [a for a in albums if a.get("cover_url")][:5]

    artist_ids = list(artists_seen)[:30]
    artists = []
    if artist_ids:
        artist_result = await db.execute(
            select(Artist)
            .where(Artist.id.in_(artist_ids))
            .order_by(Artist.lastfm_listeners.desc().nullslast())
            .limit(limit)
        )
        for a in artist_result.scalars().all():
            artists.append(
                {
                    "id": a.id,
                    "name": a.name,
                    "image_url": a.image_url or a.thumb_url,
                    "in_library": a.in_library,
                    "source": "local",
                }
            )

    return {
        "decade": decade,
        "label": f"{decade}s",
        "highlights": highlights,
        "artists": artists,
        "albums": albums,
    }


@router.get("/mood/{mood}")
async def explore_mood(
    mood: str,
    limit: int = Query(50, ge=1, le=200),
    broaden_language: bool = Query(False, description="Disable language filtering to broaden discovery"),
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Explore music by mood using local audio features + Deezer enrichment."""
    mood_profiles = {
        "energetic": {"energy": (0.7, 1.0), "tempo": (120, 200)},
        "chill": {"energy": (0.0, 0.4), "valence": (0.5, 1.0)},
        "sad": {"valence": (0.0, 0.3), "energy": (0.0, 0.4)},
        "happy": {"valence": (0.7, 1.0), "danceability": (0.6, 1.0)},
        "focus": {"instrumentalness": (0.5, 1.0), "tempo": (80, 130)},
        "workout": {
            "energy": (0.7, 1.0),
            "tempo": (120, 180),
            "danceability": (0.6, 1.0),
        },
    }
    mood_queries = {
        "energetic": "energetic dance",
        "chill": "chill ambient",
        "sad": "sad acoustic",
        "happy": "happy pop",
        "focus": "instrumental focus",
        "workout": "workout cardio",
    }

    profile = mood_profiles.get(mood, {})

    query = select(Track).join(Album, Track.album_id == Album.id)

    for feature, (low, high) in profile.items():
        if feature == "tempo":
            query = query.where(Track.tempo >= low, Track.tempo <= high)
        elif feature == "energy":
            query = query.where(Track.energy >= low, Track.energy <= high)
        elif feature == "valence":
            query = query.where(Track.valence >= low, Track.valence <= high)
        elif feature == "danceability":
            query = query.where(Track.danceability >= low, Track.danceability <= high)
        elif feature == "instrumentalness":
            query = query.where(
                Track.instrumentalness >= low, Track.instrumentalness <= high
            )

    query = query.order_by(Track.created_at.desc()).limit(limit)

    result = await db.execute(query)
    tracks_data = result.scalars().all()

    tracks = []
    album_ids_seen = set()
    albums = []

    for track in tracks_data:
        tracks.append(
            {
                "id": track.id,
                "title": track.title,
                "artist_name": (
                    track.album.artist.name
                    if track.album and track.album.artist
                    else ""
                ),
                "album_title": track.album.title if track.album else "",
                "duration_ms": track.duration_ms,
                "energy": track.energy,
                "valence": track.valence,
                "danceability": track.danceability,
                "tempo": track.tempo,
                "in_library": track.in_library,
                "source": "local",
            }
        )

        if track.album_id and track.album_id not in album_ids_seen:
            album_ids_seen.add(track.album_id)
            album = track.album
            if album:
                albums.append(
                    {
                        "id": album.id,
                        "title": album.title,
                        "artist_name": album.artist.name if album.artist else "",
                        "cover_url": album.cover_url or album.thumb_url,
                        "in_library": album.in_library,
                        "source": "local",
                    }
                )

    deezer_tracks = await deezer_service.search_tracks(
        mood_queries.get(mood, mood), limit=max(40, min(limit * 3, 150))
    )
    preferred_languages = _get_user_languages(current_user)
    mood_tokens = _tokenize(mood_queries.get(mood, mood))
    language_filtered_count = 0
    language_fallback_count = 0
    for track in deezer_tracks:
        artist = track.get("artist") or {}
        album = track.get("album") or {}
        title_blob = " ".join([track.get("title", ""), artist.get("name", ""), album.get("title", "")])
        if mood_tokens and not _contains_any_token(title_blob, mood_tokens):
            continue

        metadata_language = _extract_language_metadata(track)
        if metadata_language:
            if preferred_languages and not broaden_language and not _language_match(metadata_language, preferred_languages):
                language_filtered_count += 1
                continue
        else:
            language_fallback_count += 1

        tracks.append(
            {
                "id": f"deezer:{track.get('id')}",
                "title": track.get("title", ""),
                "artist_name": artist.get("name", ""),
                "album_title": album.get("title", ""),
                "duration_ms": (track.get("duration") or 0) * 1000,
                "in_library": False,
                "source": "deezer",
            }
        )

        if album.get("id") and not any(
            str(a.get("id")) == f"deezer:{album['id']}" for a in albums
        ):
            albums.append(
                {
                    "id": f"deezer:{album['id']}",
                    "title": album.get("title", ""),
                    "artist_name": artist.get("name", ""),
                    "cover_url": _deezer_cover(album),
                    "in_library": False,
                    "source": "deezer",
                }
            )

        if len(tracks) >= limit and len(albums) >= 20:
            break

    return {
        "mood": mood,
        "audio_profile": profile,
        "tracks": tracks[:limit],
        "albums": albums[:20],
        "language_filter": _build_language_filter_summary(
            preferred_languages=preferred_languages,
            broaden_language=broaden_language,
            filtered_count=language_filtered_count,
            no_metadata_count=language_fallback_count,
        ),
    }


@router.post("/refresh")
async def refresh_discoveries(
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger discovery refresh."""
    from app.tasks.recommendations import (
        generate_daily_recommendations,
        check_new_releases,
    )

    generate_daily_recommendations.delay()
    check_new_releases.delay()

    return {
        "status": "refresh_queued",
        "message": "Recommendations and new release check queued",
    }
