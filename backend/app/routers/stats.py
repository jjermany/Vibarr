"""Statistics and insights endpoints."""

from typing import Optional, List
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.listening_history import ListeningHistory
from app.models.artist import Artist
from app.models.album import Album

router = APIRouter()


class TopArtist(BaseModel):
    """Top artist with play count."""
    id: int
    name: str
    image_url: Optional[str] = None
    play_count: int
    total_time_ms: int


class TopAlbum(BaseModel):
    """Top album with play count."""
    id: int
    title: str
    artist_name: str
    cover_url: Optional[str] = None
    play_count: int
    total_time_ms: int


class GenreStat(BaseModel):
    """Genre statistics."""
    genre: str
    play_count: int
    percentage: float


class ListeningStats(BaseModel):
    """Overall listening statistics."""
    total_plays: int
    total_time_hours: float
    unique_artists: int
    unique_albums: int
    unique_tracks: int
    avg_plays_per_day: float
    top_artists: List[TopArtist] = []
    top_albums: List[TopAlbum] = []
    top_genres: List[GenreStat] = []


@router.get("/overview", response_model=ListeningStats)
async def get_stats_overview(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    db: AsyncSession = Depends(get_db),
):
    """Get listening statistics overview."""
    since = datetime.utcnow() - timedelta(days=days)

    # Get play count
    play_count_result = await db.execute(
        select(func.count(ListeningHistory.id))
        .where(ListeningHistory.played_at >= since)
    )
    total_plays = play_count_result.scalar() or 0

    # Get total time
    total_time_result = await db.execute(
        select(func.sum(ListeningHistory.duration_ms))
        .where(ListeningHistory.played_at >= since)
    )
    total_time_ms = total_time_result.scalar() or 0
    total_time_hours = total_time_ms / (1000 * 60 * 60)

    return ListeningStats(
        total_plays=total_plays,
        total_time_hours=round(total_time_hours, 1),
        unique_artists=0,  # TODO: Calculate
        unique_albums=0,
        unique_tracks=0,
        avg_plays_per_day=round(total_plays / days, 1) if days > 0 else 0,
        top_artists=[],
        top_albums=[],
        top_genres=[],
    )


@router.get("/top-artists")
async def get_top_artists(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Get top artists by play count."""
    since = datetime.utcnow() - timedelta(days=days)

    # TODO: Implement proper aggregation
    return {"period_days": days, "artists": []}


@router.get("/top-albums")
async def get_top_albums(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Get top albums by play count."""
    since = datetime.utcnow() - timedelta(days=days)

    # TODO: Implement proper aggregation
    return {"period_days": days, "albums": []}


@router.get("/top-tracks")
async def get_top_tracks(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Get top tracks by play count."""
    # TODO: Implement
    return {"period_days": days, "tracks": []}


@router.get("/top-genres")
async def get_top_genres(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Get top genres by play count."""
    # TODO: Implement
    return {"period_days": days, "genres": []}


@router.get("/listening-time")
async def get_listening_time(
    days: int = Query(30, ge=1, le=365),
    group_by: str = Query("day", description="Group by: hour, day, week, month"),
    db: AsyncSession = Depends(get_db),
):
    """Get listening time breakdown."""
    # TODO: Implement time series
    return {
        "period_days": days,
        "group_by": group_by,
        "data": [],
    }


@router.get("/listening-patterns")
async def get_listening_patterns(
    days: int = Query(90, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Get listening patterns (time of day, day of week)."""
    # TODO: Implement pattern analysis
    return {
        "hourly_distribution": [],
        "daily_distribution": [],
        "peak_hours": [],
        "peak_days": [],
    }


@router.get("/audio-features")
async def get_audio_feature_preferences(
    days: int = Query(90, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Get average audio feature preferences from listening history."""
    # TODO: Implement based on Spotify audio features
    return {
        "avg_danceability": 0.0,
        "avg_energy": 0.0,
        "avg_valence": 0.0,
        "avg_tempo": 0.0,
        "avg_acousticness": 0.0,
        "avg_instrumentalness": 0.0,
    }


@router.get("/discovery-stats")
async def get_discovery_stats(
    days: int = Query(90, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Get statistics about music discovery."""
    # TODO: Implement
    return {
        "new_artists_discovered": 0,
        "new_albums_discovered": 0,
        "recommendations_clicked": 0,
        "recommendations_added_to_wishlist": 0,
        "discovery_rate": 0.0,  # Percentage of new vs familiar music
    }


@router.get("/decade-breakdown")
async def get_decade_breakdown(
    days: int = Query(90, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Get listening breakdown by release decade."""
    # TODO: Implement
    return {
        "decades": [],
    }
