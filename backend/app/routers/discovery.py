"""Discovery endpoints for new music exploration."""

import asyncio
import logging
import time
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
from app.services.spotify import spotify_service
from app.services.auth import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory TTL cache for Deezer API responses (process-scoped, 10-minute TTL)
# ---------------------------------------------------------------------------
_deezer_cache: dict[str, tuple[float, Any]] = {}
_DEEZER_TTL = 600  # 10 minutes


def _deezer_cache_get(key: str) -> Any | None:
    entry = _deezer_cache.get(key)
    if entry and time.monotonic() < entry[0]:
        return entry[1]
    _deezer_cache.pop(key, None)
    return None


def _deezer_cache_set(key: str, value: Any) -> None:
    _deezer_cache[key] = (time.monotonic() + _DEEZER_TTL, value)


async def _get_artist_top_tracks_cached(artist_id, limit: int) -> list:
    key = f"top_tracks:{artist_id}:{limit}"
    hit = _deezer_cache_get(key)
    if hit is not None:
        return hit
    result = await deezer_service.get_artist_top_tracks(artist_id, limit=limit)
    _deezer_cache_set(key, result)
    return result


async def _get_artist_albums_cached(artist_id, limit: int) -> list:
    key = f"artist_albums:{artist_id}:{limit}"
    hit = _deezer_cache_get(key)
    if hit is not None:
        return hit
    result = await deezer_service.get_artist_albums(artist_id, limit=limit)
    _deezer_cache_set(key, result)
    return result


router = APIRouter()


def _tokenize(text: str) -> List[str]:
    return [t for t in (text or '').lower().replace('&', ' ').replace('-', ' ').split() if t]


def _contains_any_token(text: str, tokens: List[str]) -> bool:
    haystack = (text or '').lower()
    return any(token in haystack for token in tokens if len(token) > 2)


def _phrase_matches_token_boundaries(text: str, phrase: str) -> bool:
    """True when phrase tokens appear contiguously in text token stream."""
    phrase_tokens = _tokenize(phrase)
    text_tokens = _tokenize(text)
    if not phrase_tokens or not text_tokens or len(phrase_tokens) > len(text_tokens):
        return False
    window = len(phrase_tokens)
    return any(text_tokens[idx: idx + window] == phrase_tokens for idx in range(0, len(text_tokens) - window + 1))


def _genre_terms(genre: str) -> List[str]:
    g = (genre or '').strip().lower()
    if not g:
        return []
    terms = [g, *(_GENRE_ALIASES.get(g, []))]
    deduped: List[str] = []
    for term in terms:
        normalized = (term or '').strip().lower()
        if normalized and normalized not in deduped:
            deduped.append(normalized)
    return deduped


def _local_artist_genre_match(artist: Artist, genre: str) -> Dict[str, Any]:
    """Evaluate local artist genre evidence with strict canonical/alias matching."""
    canonical = (genre or '').strip().lower()
    aliases = set(_GENRE_ALIASES.get(canonical, []))
    artist_genres = [g.strip().lower() for g in (artist.genres or []) if isinstance(g, str) and g.strip()]
    artist_tags = [t.strip().lower() for t in (artist.tags or []) if isinstance(t, str) and t.strip()]

    if canonical in artist_genres:
        return {"include": True, "source": "canonical_genre", "confidence": 1.0}

    if any(g in aliases for g in artist_genres):
        return {"include": True, "source": "genre_alias", "confidence": 0.95}

    weak_tag_hit = any(t == canonical or t in aliases for t in artist_tags)
    if weak_tag_hit:
        return {"include": False, "source": "weak_tag_only", "confidence": 0.35}

    return {"include": False, "source": "no_match", "confidence": 0.0}


def _artist_name_relevance(name: str, genre: str) -> bool:
    """Require a strong name/token overlap for fallback genre artist search."""
    normalized_name = (name or "").strip().lower()
    normalized_genre = (genre or "").strip().lower()
    if not normalized_name or not normalized_genre:
        return False
    if normalized_genre in normalized_name:
        return True

    genre_tokens = [token for token in _tokenize(normalized_genre) if len(token) > 2]
    if not genre_tokens:
        return False

    name_tokens = set(_tokenize(normalized_name))
    matched_tokens = [token for token in genre_tokens if token in name_tokens]

    if len(genre_tokens) == 1:
        return bool(matched_tokens)
    return len(matched_tokens) >= 2


def _track_implies_genre_affinity(track: Dict[str, Any], genre: str) -> bool:
    """Use lightweight track metadata to infer fallback genre affinity."""
    genre_tokens = [token for token in _tokenize(genre) if len(token) > 2]
    if not genre_tokens:
        return False

    metadata_blob = " ".join(
        [
            track.get("title", ""),
            track.get("title_short", ""),
            (track.get("album") or {}).get("title", ""),
            (track.get("artist") or {}).get("name", ""),
        ]
    ).lower()

    if genre.lower() in metadata_blob:
        return True
    matched = [token for token in genre_tokens if token in metadata_blob]
    return len(matched) >= min(2, len(genre_tokens))


def _deezer_metadata_genre_evidence(track: Dict[str, Any], genre: str) -> bool:
    """Require exact token boundary phrase matches for canonical genre or aliases."""
    terms = _genre_terms(genre)
    if not terms:
        return False
    candidates = [
        track.get("title", ""),
        track.get("title_short", ""),
        (track.get("album") or {}).get("title", ""),
        (track.get("artist") or {}).get("name", ""),
    ]
    for text in candidates:
        if any(_phrase_matches_token_boundaries(text, term) for term in terms):
            return True
    return False


# Maps common UI genre names to Deezer genre name variants.
# Only include true name variants for the same genre — do NOT include sub-genres
# that Deezer exposes as separate genre IDs (e.g. "Dance", "House", "Indie").
# Including those causes _preferred_genre_match to pick the wrong Deezer genre
# when the sub-genre appears before the canonical one in the API response.
_GENRE_ALIASES: Dict[str, List[str]] = {
    "hip hop": ["rap/hip hop", "rap", "hip-hop", "hip hop/rap"],
    "r&b": ["r&b/soul", "r&b/soul/funk", "rhythm and blues"],
    "electronic": ["electronica", "electronic music"],
    "classical": ["classical/opera", "opera", "orchestral"],
    "alternative": ["alternative/indie", "alternative rock"],
    "country": ["country/folk", "folk/country"],
    "world": ["world music", "world/latin"],
    "metal": ["heavy metal", "hard rock/metal"],
}


def _preferred_genre_match(value: str, genre: str) -> bool:
    """Match a Deezer genre name against a UI genre name, including known aliases."""
    v = (value or "").strip().lower()
    g = (genre or "").strip().lower()
    if v == g:
        return True
    # Check if the genre's token appears in the Deezer name (e.g. "hip hop" in "rap/hip hop")
    if g and g in v:
        return True
    # Check alias mappings: the Deezer genre name must exactly equal one of the known
    # aliases for the requested UI genre.  Substring checks are intentionally omitted to
    # prevent "electro" matching "electropop", "dance" matching "dance/pop", etc.
    aliases = _GENRE_ALIASES.get(g, [])
    for alias in aliases:
        if v == alias:
            return True
    # Reverse lookup: if the Deezer genre name matches the canonical genre in _GENRE_ALIASES
    # and the requested UI genre IS that canonical, accept it.  This check is intentionally
    # restricted to g == canonical so that two different aliases of the same canonical
    # (e.g. "dance" and "house" both being aliases for "electronic") cannot cross-match
    # each other through the shared parent.
    for canonical, alias_list in _GENRE_ALIASES.items():
        if g == canonical and (v == canonical or v in [a.lower() for a in alias_list]):
            return True
    return False




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
    # Global seen-set to prevent the same artist/album appearing in multiple sections.
    # Keys are "artist:<id>", "album:<id>", or "spotify:<spotify_id>".
    _seen_home_ids: set = set()

    def _home_seen(key: str) -> bool:
        """Return True if this content key was already added to a section."""
        if key in _seen_home_ids:
            return True
        _seen_home_ids.add(key)
        return False

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
        # Skip items that have no displayable name/title (dangling recommendation refs)
        if not item.get("title") and not item.get("name") and not item.get("artist_name"):
            continue
        content_key = f"album:{rec.album_id}" if rec.album_id else f"artist:{rec.artist_id}"
        if _home_seen(content_key):
            continue
        release_section_items.append(item)

    # Spotify fallback: if no DB release radar items, use Spotify new releases
    # Only show Spotify releases if the user actually has library artists — without
    # a library the global Spotify chart is irrelevant and misleading.
    if not release_section_items and spotify_service.is_available:
        try:
            library_count_result = await db.execute(
                select(func.count(Artist.id)).where(Artist.in_library == True)
            )
            library_artist_count = library_count_result.scalar() or 0
            if library_artist_count > 0:
                spotify_releases = await spotify_service.get_new_releases(limit=20)
                for album in spotify_releases:
                    sid = album.get("id", "")
                    title = album.get("name", "")
                    if not title or not sid:
                        continue
                    key = f"spotify:{sid}"
                    if _home_seen(key):
                        continue
                    release_section_items.append({
                        "id": key,
                        "type": "album",
                        "title": title,
                        "image_url": (album.get("images") or [{}])[0].get("url") if album.get("images") else None,
                        "artist_name": (album.get("artists") or [{}])[0].get("name") if album.get("artists") else None,
                        "reason": "New release from Spotify",
                        "confidence": 0.8,
                        "source": "spotify",
                    })
        except Exception as e:
            logger.warning("Spotify new releases fallback failed: %s", e)

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
        if not rec.artist_id:
            continue
        artist = await db.execute(select(Artist).where(Artist.id == rec.artist_id))
        artist = artist.scalar_one_or_none()
        if not artist or not artist.name:
            continue
        content_key = f"artist:{rec.artist_id}"
        if _home_seen(content_key):
            continue
        similar_section_items.append({
            "id": rec.id,
            "recommendation_id": rec.id,
            "type": "artist",
            "reason": rec.reason,
            "confidence": rec.confidence_score,
            "name": artist.name,
            "image_url": artist.image_url,
            "genres": artist.genres or [],
            "in_library": artist.in_library,
        })

    # Spotify fallback: if no DB similar artist recs, use Spotify related artists
    if not similar_section_items and spotify_service.is_available:
        try:
            library_artists_result = await db.execute(
                select(Artist)
                .where(Artist.in_library == True)
                .where(Artist.spotify_id.isnot(None))
                .limit(3)
            )
            library_artists = library_artists_result.scalars().all()
            for lib_artist in library_artists:
                related = await spotify_service.get_related_artists(lib_artist.spotify_id)
                for a in related[:8]:
                    sid = a.get("id", "")
                    name = a.get("name", "")
                    if not sid or not name:
                        continue
                    key = f"spotify:{sid}"
                    if _home_seen(key):
                        continue
                    similar_section_items.append({
                        "id": key,
                        "type": "artist",
                        "name": name,
                        "image_url": (a.get("images") or [{}])[0].get("url") if a.get("images") else None,
                        "genres": a.get("genres") or [],
                        "reason": f"Related to {lib_artist.name}",
                        "confidence": 0.75,
                        "source": "spotify",
                    })
                if len(similar_section_items) >= 20:
                    break
        except Exception as e:
            logger.warning("Spotify related artists fallback failed: %s", e)

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
        item: dict = {
            "id": rec.id,
            "recommendation_id": rec.id,
            "type": "album",
            "reason": rec.reason,
            "confidence": rec.confidence_score,
        }
        content_key: str | None = None
        if rec.album_id:
            album = await db.execute(select(Album).where(Album.id == rec.album_id))
            album = album.scalar_one_or_none()
            if album and album.title:
                item["title"] = album.title
                item["image_url"] = album.cover_url
                item["in_library"] = album.in_library
                if album.artist:
                    item["artist_name"] = album.artist.name
                content_key = f"album:{rec.album_id}"
        elif rec.artist_id:
            artist = await db.execute(select(Artist).where(Artist.id == rec.artist_id))
            artist = artist.scalar_one_or_none()
            if artist and artist.name:
                item["artist_name"] = artist.name
                item["image_url"] = artist.image_url
                item["in_library"] = artist.in_library
                content_key = f"artist:{rec.artist_id}"
        # Skip items with no resolved display data or that already appeared in another section
        if not content_key:
            continue
        if _home_seen(content_key):
            continue
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
            if not (artist.genres and top_genre in artist.genres):
                continue
            if not artist.name:
                continue
            if _home_seen(f"artist:{artist.id}"):
                continue
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
        item: dict = {
            "id": rec.id,
            "recommendation_id": rec.id,
            "type": rec.recommendation_type,
            "reason": rec.reason,
            "confidence": rec.confidence_score,
        }
        content_key: str | None = None
        if rec.artist_id:
            artist = await db.execute(select(Artist).where(Artist.id == rec.artist_id))
            artist = artist.scalar_one_or_none()
            if artist and artist.name:
                item["name"] = artist.name
                item["image_url"] = artist.image_url
                item["in_library"] = artist.in_library
                content_key = f"artist:{rec.artist_id}"
        elif rec.album_id:
            album = await db.execute(select(Album).where(Album.id == rec.album_id))
            album = album.scalar_one_or_none()
            if album and album.title:
                item["name"] = album.title
                item["image_url"] = album.cover_url
                item["in_library"] = album.in_library
                content_key = f"album:{rec.album_id}"
        if not content_key:
            continue
        if _home_seen(content_key):
            continue
        discover_section_items.append(item)

    # Spotify fallback: if no DB discover weekly items, use Spotify recommendations
    if not discover_section_items and spotify_service.is_available:
        try:
            # Gather top genres from library artists
            genre_result_dw = await db.execute(
                select(Artist.genres)
                .where(Artist.in_library == True)
                .where(Artist.genres.isnot(None))
            )
            dw_genres: list = []
            for row in genre_result_dw:
                if row[0]:
                    dw_genres.extend(row[0])
            genre_counts_dw = Counter(dw_genres)
            seed_genres = [g for g, _ in genre_counts_dw.most_common(5)]
            if seed_genres:
                # Spotify accepts max 5 seeds total
                recs = await spotify_service.get_recommendations(
                    seed_genres=seed_genres[:5], limit=20
                )
                for track in recs:
                    tid = track.get("id", "")
                    name = track.get("name", "")
                    if not tid or not name:
                        continue
                    key = f"spotify:{tid}"
                    if _home_seen(key):
                        continue
                    discover_section_items.append({
                        "id": key,
                        "type": "track",
                        "name": name,
                        "artist_name": (track.get("artists") or [{}])[0].get("name") if track.get("artists") else None,
                        "image_url": (
                            (track.get("album", {}).get("images") or [{}])[0].get("url")
                            if track.get("album") and track["album"].get("images")
                            else None
                        ),
                        "reason": "Recommended based on your genres",
                        "confidence": 0.7,
                        "source": "spotify",
                    })
        except Exception as e:
            logger.warning("Spotify recommendations fallback failed: %s", e)

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
    strict: bool = Query(True, description="Require strong genre match evidence for returned items"),
    broaden_language: bool = Query(False, description="Disable language filtering to broaden discovery"),
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Explore a specific genre with local + Deezer results."""
    if not isinstance(strict, bool):
        strict = True

    # Normalise genre slug: URL slugs may use hyphens instead of spaces
    genre = genre.strip().lower().replace("-", " ")

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
    local_artist_match_by_id: Dict[int, Dict[str, Any]] = {}
    for a in result.scalars().all():
        local_match = _local_artist_genre_match(a, genre)
        if local_match["include"]:
            local_artist_match_by_id[a.id] = local_match
            artists.append(
                {
                    "id": a.id,
                    "name": a.name,
                    "image_url": a.image_url or a.thumb_url,
                    "genres": a.genres,
                    "in_library": a.in_library,
                    "popularity": a.lastfm_listeners,
                    "source": "local",
                    "genre_match_source": local_match["source"],
                    "genre_match_confidence": local_match["confidence"],
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
            artist_match = local_artist_match_by_id.get(album.artist_id, {"source": "artist_genre_context", "confidence": 0.8})
            albums.append(
                {
                    "id": album.id,
                    "title": album.title,
                    "artist_name": album.artist.name if album.artist else "",
                    "cover_url": album.cover_url or album.thumb_url,
                    "release_year": album.release_year,
                    "in_library": album.in_library,
                    "source": "local",
                    "genre_match_source": artist_match.get("source", "artist_genre_context"),
                    "genre_match_confidence": artist_match.get("confidence", 0.8),
                }
            )

    preferred_languages = _get_user_languages(current_user)
    language_filtered_count = 0
    language_fallback_count = 0

    # ---- Deezer: try the authoritative genre-artists endpoint first ----
    deezer_genres = await deezer_service.get_genres()
    deezer_genre = next(
        (g for g in deezer_genres if _preferred_genre_match(g.get("name", ""), genre)),
        None,
    )

    has_authoritative_genre_context = bool(
        deezer_genre and deezer_genre.get("id") is not None
    )

    seen_artist_ids: set = {str(a["id"]) for a in artists}
    seen_album_ids: set = {str(a["id"]) for a in albums}

    def _add_deezer_artist(
        artist_data: Dict[str, Any],
        match_source: str,
        match_confidence: float,
    ) -> bool:
        """Add a Deezer artist if not already present. Returns True if added."""
        aid = artist_data.get("id")
        if not aid:
            return False
        key = f"deezer:{aid}"
        if key in seen_artist_ids:
            return False
        seen_artist_ids.add(key)
        artists.append(
            {
                "id": key,
                "name": artist_data.get("name", ""),
                "image_url": (
                    artist_data.get("picture_xl")
                    or artist_data.get("picture_big")
                    or artist_data.get("picture_medium")
                    or artist_data.get("picture")
                ),
                "genres": [genre],
                "in_library": False,
                "popularity": artist_data.get("nb_fan") or artist_data.get("fans"),
                "source": "deezer",
                "genre_match_source": match_source,
                "genre_match_confidence": match_confidence,
            }
        )
        return True

    def _add_deezer_album(
        album_data: Dict[str, Any],
        artist_name: str = "",
        match_source: str = "artist_genre_context",
        match_confidence: float = 0.75,
    ) -> bool:
        """Add a Deezer album if not already present. Returns True if added."""
        aid = album_data.get("id")
        if not aid:
            return False
        key = f"deezer:{aid}"
        if key in seen_album_ids:
            return False
        seen_album_ids.add(key)
        release_year = None
        rd = album_data.get("release_date") or ""
        if rd and len(rd) >= 4:
            try:
                release_year = int(rd[:4])
            except ValueError:
                pass
        albums.append(
            {
                "id": key,
                "title": album_data.get("title", ""),
                "artist_name": artist_name,
                "cover_url": _deezer_cover(album_data),
                "release_year": release_year,
                "in_library": False,
                "source": "deezer",
                "genre_match_source": match_source,
                "genre_match_confidence": match_confidence,
            }
        )
        return True

    if has_authoritative_genre_context:
        deezer_artists = await deezer_service.get_genre_artists(
            deezer_genre["id"], limit=max(40, min(limit * 2, 120))
        )
        valid_deezer_artists = [a for a in deezer_artists if a.get("id")]

        if preferred_languages and not broaden_language:
            # Batch all top-track fetches in parallel, then apply language filter
            track_lists = await asyncio.gather(
                *[_get_artist_top_tracks_cached(a["id"], limit=2) for a in valid_deezer_artists],
                return_exceptions=True,
            )
            for artist, artist_top_tracks in zip(valid_deezer_artists, track_lists):
                if len(artists) >= limit:
                    break
                if isinstance(artist_top_tracks, Exception):
                    artist_top_tracks = []
                tracks_with_metadata = [
                    t for t in artist_top_tracks if _extract_language_metadata(t)
                ]
                if tracks_with_metadata:
                    has_language_match = any(
                        _language_match(_extract_language_metadata(t), preferred_languages)
                        for t in tracks_with_metadata
                    )
                    if not has_language_match:
                        language_filtered_count += 1
                        continue
                else:
                    language_fallback_count += 1
                _add_deezer_artist(artist, "deezer_genre_endpoint", 0.9)
        else:
            for artist in valid_deezer_artists:
                if len(artists) >= limit:
                    break
                _add_deezer_artist(artist, "deezer_genre_endpoint", 0.9)

    # Supplement with Deezer artist search only when authoritative genre lookup is
    # unavailable.  The broaden_language flag controls language filtering only —
    # it no longer forces a fuzzy text search which would return unrelated artists.
    should_run_search_fallback = not has_authoritative_genre_context
    search_limit = max(20, limit - len(artists))
    if should_run_search_fallback and search_limit > 0:
        search_artists = await deezer_service.search_artists(
            genre, limit=min(search_limit * 2, 50)
        )
        valid_search_artists = [a for a in search_artists if a.get("id")]
        # Batch all top-track fetches in parallel
        search_track_lists = await asyncio.gather(
            *[_get_artist_top_tracks_cached(a["id"], limit=3) for a in valid_search_artists],
            return_exceptions=True,
        )
        for artist, top_tracks in zip(valid_search_artists, search_track_lists):
            if len(artists) >= limit:
                break
            if isinstance(top_tracks, Exception):
                top_tracks = []

            strong_name_match = _artist_name_relevance(artist.get("name", ""), genre)
            strong_metadata_hit = any(
                _deezer_metadata_genre_evidence(track, genre) for track in top_tracks
            )

            if strict and not strong_metadata_hit:
                continue

            if not strong_metadata_hit and not strong_name_match:
                continue

            source = "top_track_or_album_metadata" if strong_metadata_hit else "artist_name_overlap"
            confidence = 0.85 if strong_metadata_hit else 0.55
            _add_deezer_artist(artist, source, confidence)

    # Fetch albums for Deezer artists that have few/no albums represented
    deezer_artist_ids = [
        a["id"].replace("deezer:", "")
        for a in artists
        if str(a.get("id", "")).startswith("deezer:")
    ]
    batch_ids = deezer_artist_ids[:15]
    if batch_ids:
        album_batches = await asyncio.gather(
            *[_get_artist_albums_cached(da_id, limit=3) for da_id in batch_ids],
            return_exceptions=True,
        )
        for da_id, artist_albums in zip(batch_ids, album_batches):
            if len(albums) >= limit:
                break
            if isinstance(artist_albums, Exception):
                continue
            artist_name = next(
                (a["name"] for a in artists if a.get("id") == f"deezer:{da_id}"), ""
            )
            artist_match = next(
                (a for a in artists if a.get("id") == f"deezer:{da_id}"), {}
            )
            for alb in artist_albums:
                if len(albums) >= limit:
                    break
                _add_deezer_album(
                    alb,
                    artist_name,
                    match_source=artist_match.get("genre_match_source", "artist_genre_context"),
                    match_confidence=artist_match.get("genre_match_confidence", 0.75),
                )

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
        "strict": strict,
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
