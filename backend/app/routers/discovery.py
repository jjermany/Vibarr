"""Discovery endpoints for new music exploration."""

from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter()


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

    Returns curated sections:
    - Your weekly discoveries
    - New releases from artists you follow
    - Because you listened to X
    - Genre deep dives
    - Time machine (decade exploration)
    """
    sections = [
        {
            "id": "discover_weekly",
            "title": "Discover Weekly",
            "description": "Fresh picks based on your taste",
            "type": "playlist",
            "items": [],
        },
        {
            "id": "release_radar",
            "title": "Release Radar",
            "description": "New releases from artists you follow",
            "type": "album_list",
            "items": [],
        },
        {
            "id": "similar_to_recent",
            "title": "Because You Listened To...",
            "description": "Artists similar to your recent plays",
            "type": "artist_list",
            "items": [],
        },
        {
            "id": "deep_cuts",
            "title": "Deep Cuts",
            "description": "Hidden gems from artists you know",
            "type": "album_list",
            "items": [],
        },
        {
            "id": "genre_spotlight",
            "title": "Genre Spotlight",
            "description": "Explore your favorite genres",
            "type": "genre_list",
            "items": [],
        },
    ]

    return {"sections": sections}


@router.get("/playlists")
async def get_discovery_playlists(
    db: AsyncSession = Depends(get_db),
):
    """Get all generated discovery playlists."""
    # TODO: Return actual generated playlists
    playlists = [
        DiscoveryPlaylist(
            id="discover_weekly",
            name="Discover Weekly",
            description="Your weekly mix of fresh music",
            track_count=30,
            generated_at="2024-01-01T00:00:00Z",
        ),
        DiscoveryPlaylist(
            id="release_radar",
            name="Release Radar",
            description="New music from artists you follow",
            track_count=20,
            generated_at="2024-01-01T00:00:00Z",
        ),
    ]

    return {"playlists": playlists}


@router.get("/similar/{artist_id}")
async def get_similar_discoveries(
    artist_id: int,
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Get discovery suggestions based on a specific artist."""
    # TODO: Implement via Last.fm similar artists + Spotify
    return {
        "based_on_artist_id": artist_id,
        "artists": [],
        "albums": [],
    }


@router.get("/genre/{genre}")
async def explore_genre(
    genre: str,
    sort: str = Query("popular", description="Sort: popular, recent, random"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Explore a specific genre."""
    return {
        "genre": genre,
        "artists": [],
        "albums": [],
        "related_genres": [],
    }


@router.get("/decade/{decade}")
async def explore_decade(
    decade: int,
    genre: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Time machine - explore a specific decade."""
    return {
        "decade": decade,
        "highlights": [],
        "artists": [],
        "albums": [],
    }


@router.get("/mood/{mood}")
async def explore_mood(
    mood: str,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """
    Explore music by mood using audio features.

    Moods map to audio feature combinations:
    - energetic: high energy, high tempo
    - chill: low energy, high valence
    - sad: low valence, low energy
    - happy: high valence, high danceability
    - focus: high instrumentalness, moderate tempo
    - workout: high energy, high tempo, high danceability
    """
    mood_profiles = {
        "energetic": {"energy": (0.7, 1.0), "tempo": (120, 200)},
        "chill": {"energy": (0.0, 0.4), "valence": (0.5, 1.0)},
        "sad": {"valence": (0.0, 0.3), "energy": (0.0, 0.4)},
        "happy": {"valence": (0.7, 1.0), "danceability": (0.6, 1.0)},
        "focus": {"instrumentalness": (0.5, 1.0), "tempo": (80, 130)},
        "workout": {"energy": (0.7, 1.0), "tempo": (120, 180), "danceability": (0.6, 1.0)},
    }

    profile = mood_profiles.get(mood, {})

    return {
        "mood": mood,
        "audio_profile": profile,
        "tracks": [],
        "albums": [],
    }


@router.post("/refresh")
async def refresh_discoveries(
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger discovery refresh."""
    # TODO: Queue Celery task to regenerate recommendations
    return {"status": "refresh_queued"}
