"""Statistics and insights endpoints."""

import logging
from typing import Optional, List
from datetime import datetime, timedelta
from collections import Counter

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, func, distinct, case, extract
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.listening_history import ListeningHistory
from app.models.artist import Artist
from app.models.album import Album
from app.models.track import Track
from app.models.recommendation import Recommendation
from app.services.advanced_recommendations import calculate_listening_streak, calculate_library_growth

logger = logging.getLogger(__name__)

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


class TopTrack(BaseModel):
    """Top track with play count."""
    id: int
    title: str
    artist_name: str
    album_title: str
    play_count: int
    total_time_ms: int
    skip_rate: float


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

    # Get unique counts
    unique_artists_result = await db.execute(
        select(func.count(distinct(ListeningHistory.artist_id)))
        .where(ListeningHistory.played_at >= since)
        .where(ListeningHistory.artist_id.isnot(None))
    )
    unique_artists = unique_artists_result.scalar() or 0

    unique_albums_result = await db.execute(
        select(func.count(distinct(ListeningHistory.album_id)))
        .where(ListeningHistory.played_at >= since)
        .where(ListeningHistory.album_id.isnot(None))
    )
    unique_albums = unique_albums_result.scalar() or 0

    unique_tracks_result = await db.execute(
        select(func.count(distinct(ListeningHistory.track_id)))
        .where(ListeningHistory.played_at >= since)
        .where(ListeningHistory.track_id.isnot(None))
    )
    unique_tracks = unique_tracks_result.scalar() or 0

    # Get top artists
    top_artists = await _get_top_artists(db, since, limit=5)

    # Get top albums
    top_albums = await _get_top_albums(db, since, limit=5)

    # Get top genres
    top_genres = await _get_top_genres(db, since, limit=10)

    return ListeningStats(
        total_plays=total_plays,
        total_time_hours=round(total_time_hours, 1),
        unique_artists=unique_artists,
        unique_albums=unique_albums,
        unique_tracks=unique_tracks,
        avg_plays_per_day=round(total_plays / max(days, 1), 1),
        top_artists=top_artists,
        top_albums=top_albums,
        top_genres=top_genres,
    )


async def _get_top_artists(db: AsyncSession, since: datetime, limit: int) -> List[TopArtist]:
    """Get top artists by play count in period."""
    result = await db.execute(
        select(
            Artist.id,
            Artist.name,
            Artist.image_url,
            func.count(ListeningHistory.id).label("play_count"),
            func.coalesce(func.sum(ListeningHistory.duration_ms), 0).label("total_time_ms"),
        )
        .join(ListeningHistory, ListeningHistory.artist_id == Artist.id)
        .where(ListeningHistory.played_at >= since)
        .group_by(Artist.id, Artist.name, Artist.image_url)
        .order_by(func.count(ListeningHistory.id).desc())
        .limit(limit)
    )
    rows = result.all()
    return [
        TopArtist(
            id=row.id,
            name=row.name,
            image_url=row.image_url,
            play_count=row.play_count,
            total_time_ms=row.total_time_ms,
        )
        for row in rows
    ]


async def _get_top_albums(db: AsyncSession, since: datetime, limit: int) -> List[TopAlbum]:
    """Get top albums by play count in period."""
    result = await db.execute(
        select(
            Album.id,
            Album.title,
            Artist.name.label("artist_name"),
            Album.cover_url,
            func.count(ListeningHistory.id).label("play_count"),
            func.coalesce(func.sum(ListeningHistory.duration_ms), 0).label("total_time_ms"),
        )
        .join(ListeningHistory, ListeningHistory.album_id == Album.id)
        .join(Artist, Album.artist_id == Artist.id)
        .where(ListeningHistory.played_at >= since)
        .group_by(Album.id, Album.title, Artist.name, Album.cover_url)
        .order_by(func.count(ListeningHistory.id).desc())
        .limit(limit)
    )
    rows = result.all()
    return [
        TopAlbum(
            id=row.id,
            title=row.title,
            artist_name=row.artist_name,
            cover_url=row.cover_url,
            play_count=row.play_count,
            total_time_ms=row.total_time_ms,
        )
        for row in rows
    ]


async def _get_top_genres(db: AsyncSession, since: datetime, limit: int) -> List[GenreStat]:
    """Get top genres from listening history."""
    # Get artist IDs from listening history
    result = await db.execute(
        select(ListeningHistory.artist_id)
        .where(ListeningHistory.played_at >= since)
        .where(ListeningHistory.artist_id.isnot(None))
    )
    artist_ids_with_dupes = [row[0] for row in result.all()]

    if not artist_ids_with_dupes:
        return []

    # Count how many plays per artist
    artist_play_counts = Counter(artist_ids_with_dupes)
    unique_artist_ids = list(artist_play_counts.keys())

    # Get genres for those artists
    artist_result = await db.execute(
        select(Artist.id, Artist.genres)
        .where(Artist.id.in_(unique_artist_ids))
        .where(Artist.genres.isnot(None))
    )
    artist_genres = artist_result.all()

    # Weight genres by play count
    genre_counts = Counter()
    for artist_id, genres in artist_genres:
        if genres:
            play_count = artist_play_counts.get(artist_id, 0)
            for genre in genres:
                genre_counts[genre] += play_count

    total = sum(genre_counts.values())
    if total == 0:
        return []

    return [
        GenreStat(
            genre=genre,
            play_count=count,
            percentage=round(count / total * 100, 1),
        )
        for genre, count in genre_counts.most_common(limit)
    ]


@router.get("/top-artists")
async def get_top_artists(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Get top artists by play count."""
    since = datetime.utcnow() - timedelta(days=days)
    artists = await _get_top_artists(db, since, limit)
    return {"period_days": days, "artists": [a.model_dump() for a in artists]}


@router.get("/top-albums")
async def get_top_albums(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Get top albums by play count."""
    since = datetime.utcnow() - timedelta(days=days)
    albums = await _get_top_albums(db, since, limit)
    return {"period_days": days, "albums": [a.model_dump() for a in albums]}


@router.get("/top-tracks")
async def get_top_tracks(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Get top tracks by play count."""
    since = datetime.utcnow() - timedelta(days=days)

    result = await db.execute(
        select(
            Track.id,
            Track.title,
            Artist.name.label("artist_name"),
            Album.title.label("album_title"),
            func.count(ListeningHistory.id).label("play_count"),
            func.coalesce(func.sum(ListeningHistory.duration_ms), 0).label("total_time_ms"),
            func.avg(
                case(
                    (ListeningHistory.was_skipped == True, 1.0),
                    else_=0.0,
                )
            ).label("skip_rate"),
        )
        .join(ListeningHistory, ListeningHistory.track_id == Track.id)
        .join(Album, Track.album_id == Album.id)
        .join(Artist, Album.artist_id == Artist.id)
        .where(ListeningHistory.played_at >= since)
        .group_by(Track.id, Track.title, Artist.name, Album.title)
        .order_by(func.count(ListeningHistory.id).desc())
        .limit(limit)
    )
    rows = result.all()

    tracks = [
        {
            "id": row.id,
            "title": row.title,
            "artist_name": row.artist_name,
            "album_title": row.album_title,
            "play_count": row.play_count,
            "total_time_ms": row.total_time_ms,
            "skip_rate": round(float(row.skip_rate or 0), 2),
        }
        for row in rows
    ]
    return {"period_days": days, "tracks": tracks}


@router.get("/top-genres")
async def get_top_genres(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Get top genres by play count."""
    since = datetime.utcnow() - timedelta(days=days)
    genres = await _get_top_genres(db, since, limit)
    return {"period_days": days, "genres": [g.model_dump() for g in genres]}


@router.get("/listening-time")
async def get_listening_time(
    days: int = Query(30, ge=1, le=365),
    group_by: str = Query("day", description="Group by: hour, day, week, month"),
    db: AsyncSession = Depends(get_db),
):
    """Get listening time breakdown."""
    since = datetime.utcnow() - timedelta(days=days)

    result = await db.execute(
        select(
            func.date_trunc(group_by, ListeningHistory.played_at).label("period"),
            func.count(ListeningHistory.id).label("play_count"),
            func.coalesce(func.sum(ListeningHistory.duration_ms), 0).label("total_time_ms"),
        )
        .where(ListeningHistory.played_at >= since)
        .group_by(func.date_trunc(group_by, ListeningHistory.played_at))
        .order_by(func.date_trunc(group_by, ListeningHistory.played_at))
    )
    rows = result.all()

    data = [
        {
            "period": row.period.isoformat() if row.period else None,
            "play_count": row.play_count,
            "total_time_ms": row.total_time_ms,
            "total_time_hours": round(row.total_time_ms / (1000 * 60 * 60), 2),
        }
        for row in rows
    ]

    return {
        "period_days": days,
        "group_by": group_by,
        "data": data,
    }


@router.get("/listening-patterns")
async def get_listening_patterns(
    days: int = Query(90, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Get listening patterns (time of day, day of week)."""
    since = datetime.utcnow() - timedelta(days=days)

    # Hourly distribution
    hourly_result = await db.execute(
        select(
            ListeningHistory.hour_of_day,
            func.count(ListeningHistory.id).label("play_count"),
        )
        .where(ListeningHistory.played_at >= since)
        .where(ListeningHistory.hour_of_day.isnot(None))
        .group_by(ListeningHistory.hour_of_day)
        .order_by(ListeningHistory.hour_of_day)
    )
    hourly_rows = hourly_result.all()
    hourly_distribution = [
        {"hour": row.hour_of_day, "play_count": row.play_count}
        for row in hourly_rows
    ]

    # Daily distribution
    daily_result = await db.execute(
        select(
            ListeningHistory.day_of_week,
            func.count(ListeningHistory.id).label("play_count"),
        )
        .where(ListeningHistory.played_at >= since)
        .where(ListeningHistory.day_of_week.isnot(None))
        .group_by(ListeningHistory.day_of_week)
        .order_by(ListeningHistory.day_of_week)
    )
    daily_rows = daily_result.all()

    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    daily_distribution = [
        {
            "day": row.day_of_week,
            "day_name": day_names[row.day_of_week] if row.day_of_week < 7 else "Unknown",
            "play_count": row.play_count,
        }
        for row in daily_rows
    ]

    # Find peaks
    peak_hours = sorted(hourly_rows, key=lambda r: r.play_count, reverse=True)[:3]
    peak_days = sorted(daily_rows, key=lambda r: r.play_count, reverse=True)[:3]

    return {
        "hourly_distribution": hourly_distribution,
        "daily_distribution": daily_distribution,
        "peak_hours": [r.hour_of_day for r in peak_hours],
        "peak_days": [r.day_of_week for r in peak_days],
    }


@router.get("/audio-features")
async def get_audio_feature_preferences(
    days: int = Query(90, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Get average audio feature preferences from listening history."""
    since = datetime.utcnow() - timedelta(days=days)

    # Get tracks from listening history that have audio features
    result = await db.execute(
        select(
            func.avg(Track.danceability).label("avg_danceability"),
            func.avg(Track.energy).label("avg_energy"),
            func.avg(Track.valence).label("avg_valence"),
            func.avg(Track.tempo).label("avg_tempo"),
            func.avg(Track.acousticness).label("avg_acousticness"),
            func.avg(Track.instrumentalness).label("avg_instrumentalness"),
            func.avg(Track.speechiness).label("avg_speechiness"),
            func.avg(Track.liveness).label("avg_liveness"),
        )
        .join(ListeningHistory, ListeningHistory.track_id == Track.id)
        .where(ListeningHistory.played_at >= since)
        .where(Track.danceability.isnot(None))
    )
    row = result.one_or_none()

    if row:
        return {
            "avg_danceability": round(float(row.avg_danceability or 0), 3),
            "avg_energy": round(float(row.avg_energy or 0), 3),
            "avg_valence": round(float(row.avg_valence or 0), 3),
            "avg_tempo": round(float(row.avg_tempo or 0), 1),
            "avg_acousticness": round(float(row.avg_acousticness or 0), 3),
            "avg_instrumentalness": round(float(row.avg_instrumentalness or 0), 3),
            "avg_speechiness": round(float(row.avg_speechiness or 0), 3),
            "avg_liveness": round(float(row.avg_liveness or 0), 3),
        }

    return {
        "avg_danceability": 0.0,
        "avg_energy": 0.0,
        "avg_valence": 0.0,
        "avg_tempo": 0.0,
        "avg_acousticness": 0.0,
        "avg_instrumentalness": 0.0,
        "avg_speechiness": 0.0,
        "avg_liveness": 0.0,
    }


@router.get("/discovery-stats")
async def get_discovery_stats(
    days: int = Query(90, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Get statistics about music discovery."""
    since = datetime.utcnow() - timedelta(days=days)

    # New artists discovered (first listen in period)
    new_artists_result = await db.execute(
        select(func.count(distinct(ListeningHistory.artist_id)))
        .where(ListeningHistory.played_at >= since)
        .where(ListeningHistory.artist_id.isnot(None))
        .where(
            ~ListeningHistory.artist_id.in_(
                select(distinct(ListeningHistory.artist_id))
                .where(ListeningHistory.played_at < since)
                .where(ListeningHistory.artist_id.isnot(None))
            )
        )
    )
    new_artists = new_artists_result.scalar() or 0

    # New albums discovered
    new_albums_result = await db.execute(
        select(func.count(distinct(ListeningHistory.album_id)))
        .where(ListeningHistory.played_at >= since)
        .where(ListeningHistory.album_id.isnot(None))
        .where(
            ~ListeningHistory.album_id.in_(
                select(distinct(ListeningHistory.album_id))
                .where(ListeningHistory.played_at < since)
                .where(ListeningHistory.album_id.isnot(None))
            )
        )
    )
    new_albums = new_albums_result.scalar() or 0

    # Recommendation interaction stats
    rec_clicked_result = await db.execute(
        select(func.count(Recommendation.id))
        .where(Recommendation.clicked == True)
        .where(Recommendation.created_at >= since)
    )
    recommendations_clicked = rec_clicked_result.scalar() or 0

    rec_wishlisted_result = await db.execute(
        select(func.count(Recommendation.id))
        .where(Recommendation.added_to_wishlist == True)
        .where(Recommendation.created_at >= since)
    )
    recommendations_wishlisted = rec_wishlisted_result.scalar() or 0

    # Total unique artists in period vs all time
    total_artists_in_period = await db.execute(
        select(func.count(distinct(ListeningHistory.artist_id)))
        .where(ListeningHistory.played_at >= since)
        .where(ListeningHistory.artist_id.isnot(None))
    )
    total_in_period = total_artists_in_period.scalar() or 0

    discovery_rate = round(new_artists / max(total_in_period, 1) * 100, 1)

    return {
        "new_artists_discovered": new_artists,
        "new_albums_discovered": new_albums,
        "recommendations_clicked": recommendations_clicked,
        "recommendations_added_to_wishlist": recommendations_wishlisted,
        "discovery_rate": discovery_rate,
    }


@router.get("/decade-breakdown")
async def get_decade_breakdown(
    days: int = Query(90, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Get listening breakdown by release decade."""
    since = datetime.utcnow() - timedelta(days=days)

    result = await db.execute(
        select(
            Album.release_year,
            func.count(ListeningHistory.id).label("play_count"),
        )
        .join(ListeningHistory, ListeningHistory.album_id == Album.id)
        .where(ListeningHistory.played_at >= since)
        .where(Album.release_year.isnot(None))
        .group_by(Album.release_year)
    )
    rows = result.all()

    # Group by decade
    decade_counts = Counter()
    for year, play_count in rows:
        if year:
            decade = (year // 10) * 10
            decade_counts[decade] += play_count

    total = sum(decade_counts.values())
    decades = [
        {
            "decade": decade,
            "label": f"{decade}s",
            "play_count": count,
            "percentage": round(count / max(total, 1) * 100, 1),
        }
        for decade, count in sorted(decade_counts.items())
    ]

    return {"decades": decades}


@router.get("/streak")
async def get_listening_streak(
    db: AsyncSession = Depends(get_db),
):
    """Get current and longest listening streaks."""
    result = await db.execute(
        select(ListeningHistory.played_at)
        .order_by(ListeningHistory.played_at)
    )
    play_dates = [row[0] for row in result.all() if row[0]]
    streak_data = calculate_listening_streak(play_dates)
    return streak_data


@router.get("/library-growth")
async def get_library_growth(
    days: int = Query(90, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Get library growth over time (albums added per day)."""
    result = await db.execute(
        select(Album.created_at)
        .where(Album.in_library == True)
    )
    items = [{"created_at": row[0]} for row in result.all() if row[0]]
    growth = calculate_library_growth(items, days=days)
    return {"growth": growth}


@router.get("/comparison")
async def get_period_comparison(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Compare current period stats with the previous period."""
    now = datetime.utcnow()
    current_start = now - timedelta(days=days)
    previous_start = current_start - timedelta(days=days)

    # Current period
    current_plays_result = await db.execute(
        select(func.count(ListeningHistory.id))
        .where(ListeningHistory.played_at >= current_start)
    )
    current_plays = current_plays_result.scalar() or 0

    current_time_result = await db.execute(
        select(func.coalesce(func.sum(ListeningHistory.duration_ms), 0))
        .where(ListeningHistory.played_at >= current_start)
    )
    current_time_ms = current_time_result.scalar() or 0

    current_artists_result = await db.execute(
        select(func.count(distinct(ListeningHistory.artist_id)))
        .where(ListeningHistory.played_at >= current_start)
        .where(ListeningHistory.artist_id.isnot(None))
    )
    current_artists = current_artists_result.scalar() or 0

    # Previous period
    previous_plays_result = await db.execute(
        select(func.count(ListeningHistory.id))
        .where(ListeningHistory.played_at >= previous_start)
        .where(ListeningHistory.played_at < current_start)
    )
    previous_plays = previous_plays_result.scalar() or 0

    previous_time_result = await db.execute(
        select(func.coalesce(func.sum(ListeningHistory.duration_ms), 0))
        .where(ListeningHistory.played_at >= previous_start)
        .where(ListeningHistory.played_at < current_start)
    )
    previous_time_ms = previous_time_result.scalar() or 0

    previous_artists_result = await db.execute(
        select(func.count(distinct(ListeningHistory.artist_id)))
        .where(ListeningHistory.played_at >= previous_start)
        .where(ListeningHistory.played_at < current_start)
        .where(ListeningHistory.artist_id.isnot(None))
    )
    previous_artists = previous_artists_result.scalar() or 0

    def pct_change(current, previous):
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        return round((current - previous) / previous * 100, 1)

    return {
        "period_days": days,
        "current": {
            "plays": current_plays,
            "time_hours": round(current_time_ms / (1000 * 60 * 60), 1),
            "unique_artists": current_artists,
        },
        "previous": {
            "plays": previous_plays,
            "time_hours": round(previous_time_ms / (1000 * 60 * 60), 1),
            "unique_artists": previous_artists,
        },
        "changes": {
            "plays_pct": pct_change(current_plays, previous_plays),
            "time_pct": pct_change(current_time_ms, previous_time_ms),
            "artists_pct": pct_change(current_artists, previous_artists),
        },
    }
