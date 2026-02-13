"""Recommendation generation tasks."""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from collections import Counter

from app.celery_app import celery_app
from app.database import AsyncSessionLocal
from app.services.spotify import spotify_service
from app.services.lastfm import lastfm_service
from app.services.deezer import deezer_service
from app.services.advanced_recommendations import (
    build_artist_affinity_matrix,
    build_genre_affinity,
    score_recommendation_advanced,
    diversify_recommendations,
)
from app.models.artist import Artist
from app.models.album import Album
from app.models.track import Track
from app.models.recommendation import Recommendation
from app.models.listening_history import ListeningHistory
from app.models.user_preference import TasteProfile, UserPreference

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.recommendations.generate_daily_recommendations")
def generate_daily_recommendations():
    """Generate daily recommendation playlists."""
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_generate_daily_recommendations_async())
    finally:
        loop.close()


async def _generate_daily_recommendations_async():
    """Async implementation of daily recommendations with advanced scoring."""
    logger.info("Generating daily recommendations (Phase 4 advanced engine)")

    async with AsyncSessionLocal() as db:
        # Clear expired recommendations
        from sqlalchemy import delete
        await db.execute(
            delete(Recommendation).where(
                Recommendation.expires_at < datetime.utcnow()
            )
        )
        await db.commit()

        recommendations_created = 0

        # Get taste profile for scoring
        taste_profile = await _get_current_taste_profile(db)

        # Build advanced affinity matrices from recent listening
        artist_affinity, genre_aff = await _build_affinity_data(db)

        # Generate similar artist recommendations
        similar_recs = await _generate_similar_artist_recommendations(
            db, taste_profile, artist_affinity=artist_affinity, genre_affinity=genre_aff,
        )
        recommendations_created += len(similar_recs)

        # Generate genre-based recommendations
        genre_recs = await _generate_genre_recommendations(db, taste_profile)
        recommendations_created += len(genre_recs)

        # Generate deep cuts recommendations
        deep_cut_recs = await _generate_deep_cuts_recommendations(db, taste_profile)
        recommendations_created += len(deep_cut_recs)

        # Generate mood-based recommendations
        mood_recs = await _generate_mood_recommendations(db, taste_profile)
        recommendations_created += len(mood_recs)

        # Generate listening-history-based recommendations
        history_recs = await _generate_history_based_recommendations(
            db, taste_profile, artist_affinity=artist_affinity, genre_affinity=genre_aff,
        )
        recommendations_created += len(history_recs)

        # Apply diversity boosting across all recommendations
        all_rec_dicts = []
        all_rec_objects = similar_recs + genre_recs + deep_cut_recs + mood_recs + history_recs
        for rec in all_rec_objects:
            all_rec_dicts.append({
                "obj": rec,
                "artist_id": rec.artist_id,
                "based_on_artist_id": rec.based_on_artist_id,
                "category": rec.category,
                "confidence_score": rec.confidence_score,
            })

        diversified = diversify_recommendations(all_rec_dicts)
        diversified_objects = [d["obj"] for d in diversified]

        for rec in diversified_objects:
            db.add(rec)

        await db.commit()
        recommendations_created = len(diversified_objects)

        return {
            "status": "completed",
            "recommendations_created": recommendations_created,
            "pre_diversity_count": len(all_rec_objects),
            "breakdown": {
                "similar_artists": len(similar_recs),
                "genre_explore": len(genre_recs),
                "deep_cuts": len(deep_cut_recs),
                "mood_based": len(mood_recs),
                "history_based": len(history_recs),
            },
        }


async def _build_affinity_data(db) -> tuple:
    """Build artist and genre affinity matrices from recent listening history."""
    from sqlalchemy import select

    since = datetime.utcnow() - timedelta(days=90)
    result = await db.execute(
        select(
            ListeningHistory.artist_id,
            ListeningHistory.played_at,
            ListeningHistory.completion_percentage,
            ListeningHistory.was_skipped,
        )
        .where(ListeningHistory.played_at >= since)
        .where(ListeningHistory.artist_id.isnot(None))
    )
    rows = result.all()

    history_dicts = [
        {
            "artist_id": row.artist_id,
            "played_at": row.played_at,
            "completion_percentage": row.completion_percentage,
            "was_skipped": row.was_skipped,
        }
        for row in rows
    ]

    artist_affinity = build_artist_affinity_matrix(history_dicts)

    # Get artist genres for genre affinity
    artist_ids = list(set(r["artist_id"] for r in history_dicts if r["artist_id"]))
    artist_genres_map = {}
    if artist_ids:
        artist_result = await db.execute(
            select(Artist.id, Artist.genres)
            .where(Artist.id.in_(artist_ids))
            .where(Artist.genres.isnot(None))
        )
        for aid, genres in artist_result.all():
            if genres:
                artist_genres_map[aid] = genres

    genre_aff = build_genre_affinity(history_dicts, artist_genres_map)

    return artist_affinity, genre_aff


async def _get_current_taste_profile(db) -> Dict[str, Any]:
    """Get current taste profile or build a basic one."""
    from sqlalchemy import select

    result = await db.execute(
        select(TasteProfile).order_by(TasteProfile.version.desc()).limit(1)
    )
    profile = result.scalar_one_or_none()

    if profile:
        return {
            "top_genres": profile.top_genres or [],
            "genre_weights": profile.genre_weights or {},
            "preferred_decades": profile.preferred_decades or [],
            "decade_weights": profile.decade_weights or {},
            "avg_danceability": profile.avg_danceability,
            "avg_energy": profile.avg_energy,
            "avg_valence": profile.avg_valence,
            "avg_tempo": profile.avg_tempo,
            "novelty_preference": profile.novelty_preference,
            "total_plays": profile.total_plays,
            "peak_listening_hours": profile.peak_listening_hours or [],
        }

    # Build basic profile from library if no taste profile exists
    return await _build_basic_profile(db)


async def _build_basic_profile(db) -> Dict[str, Any]:
    """Build basic taste profile from library data."""
    from sqlalchemy import select

    result = await db.execute(
        select(Artist.genres)
        .where(Artist.in_library == True)
        .where(Artist.genres.isnot(None))
    )
    all_genres = []
    for row in result:
        if row[0]:
            all_genres.extend(row[0])

    genre_counts = Counter(all_genres)
    total = sum(genre_counts.values()) or 1
    genre_weights = {g: c / total for g, c in genre_counts.most_common(20)}
    top_genres = list(genre_weights.keys())

    return {
        "top_genres": top_genres,
        "genre_weights": genre_weights,
        "preferred_decades": [],
        "decade_weights": {},
        "avg_danceability": None,
        "avg_energy": None,
        "avg_valence": None,
        "avg_tempo": None,
        "novelty_preference": 0.5,
        "total_plays": 0,
        "peak_listening_hours": [],
    }


def _score_recommendation(taste_profile: Dict, artist_genres: List[str] = None,
                          audio_features: Dict = None) -> float:
    """Calculate a confidence score based on how well an item matches the taste profile."""
    score = 0.5  # Base score

    # Genre matching (up to +0.3)
    if artist_genres and taste_profile.get("genre_weights"):
        genre_score = 0
        for genre in artist_genres:
            weight = taste_profile["genre_weights"].get(genre, 0)
            genre_score += weight
        score += min(genre_score, 0.3)

    # Audio feature matching (up to +0.2)
    if audio_features and taste_profile.get("avg_energy") is not None:
        feature_diff = 0
        count = 0
        for feature in ["danceability", "energy", "valence"]:
            profile_val = taste_profile.get(f"avg_{feature}")
            item_val = audio_features.get(feature)
            if profile_val is not None and item_val is not None:
                feature_diff += abs(profile_val - item_val)
                count += 1
        if count > 0:
            avg_diff = feature_diff / count
            # Lower difference = higher score
            score += max(0, 0.2 - avg_diff * 0.4)

    return min(score, 1.0)


async def _generate_similar_artist_recommendations(
    db, taste_profile: Dict,
    artist_affinity: Dict[int, float] = None,
    genre_affinity: Dict[str, float] = None,
) -> List[Recommendation]:
    """Generate recommendations based on similar artists with advanced scoring."""
    recommendations = []
    artist_affinity = artist_affinity or {}
    genre_affinity = genre_affinity or {}

    if not lastfm_service.is_available:
        return recommendations

    from sqlalchemy import select, func
    result = await db.execute(
        select(Artist)
        .where(Artist.in_library == True)
        .order_by(Artist.lastfm_playcount.desc().nullslast())
        .limit(20)
    )
    top_artists = result.scalars().all()

    # Get feedback history for the similar_artists category
    feedback = await _get_category_feedback(db, "similar_artists")

    for artist in top_artists:
        try:
            similar = await lastfm_service.get_similar_artists(artist.name, limit=5)

            for similar_artist in similar:
                # Check if already in library
                existing = await db.execute(
                    select(Artist).where(
                        func.lower(Artist.name) == similar_artist["name"].lower(),
                        Artist.in_library == True,
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                # Check if artist exists in our DB
                artist_result = await db.execute(
                    select(Artist).where(
                        func.lower(Artist.name) == similar_artist["name"].lower()
                    )
                )
                db_artist = artist_result.scalar_one_or_none()

                # Use advanced scoring
                match_score = similar_artist.get("match", 0.5)
                item_genres = db_artist.genres if db_artist and db_artist.genres else []

                confidence, score_factors = score_recommendation_advanced(
                    taste_profile=taste_profile,
                    artist_affinity=artist_affinity,
                    genre_affinity=genre_affinity,
                    item_artist_id=db_artist.id if db_artist else None,
                    item_genres=item_genres,
                    based_on_artist_id=artist.id,
                    similarity_score=match_score,
                    feedback_history=feedback,
                )

                rec = Recommendation(
                    recommendation_type="artist",
                    artist_id=db_artist.id if db_artist else None,
                    category="similar_artists",
                    reason=f"Similar to {artist.name}",
                    reason_items=[f"Because you have {artist.name} in your library"],
                    based_on_artist_id=artist.id,
                    confidence_score=confidence,
                    relevance_score=round(match_score, 3),
                    novelty_score=score_factors.get("novelty", 0.8),
                    score_factors=score_factors,
                    expires_at=datetime.utcnow() + timedelta(days=7),
                )
                recommendations.append(rec)

        except Exception as e:
            logger.error(f"Error getting similar artists for {artist.name}: {e}")
            continue

    return recommendations


async def _generate_genre_recommendations(db, taste_profile: Dict) -> List[Recommendation]:
    """Generate recommendations based on genre preferences using Deezer.

    Spotify's /recommendations endpoint was deprecated in November 2024, so we
    use Deezer's genre artist lists as the recommendation source.
    """
    recommendations = []

    from sqlalchemy import func, select

    top_genres = taste_profile.get("top_genres", [])[:5]
    if not top_genres:
        # Fall back to library genres
        result = await db.execute(
            select(Artist.genres)
            .where(Artist.in_library == True)
            .where(Artist.genres.isnot(None))
        )
        all_genres = []
        for row in result:
            if row[0]:
                all_genres.extend(row[0])
        if not all_genres:
            return recommendations
        genre_counts = Counter(all_genres)
        top_genres = [g for g, _ in genre_counts.most_common(5)]

    try:
        deezer_genres = await deezer_service.get_genres()
        genre_id_map = {g.get("name", "").lower(): g.get("id") for g in deezer_genres}

        seen_names: set = set()
        for genre in top_genres[:3]:
            genre_lower = genre.lower()
            # Try exact match first, then partial match
            genre_id = genre_id_map.get(genre_lower)
            if not genre_id:
                for deezer_name, gid in genre_id_map.items():
                    if genre_lower in deezer_name or deezer_name in genre_lower:
                        genre_id = gid
                        break

            if not genre_id:
                continue

            deezer_artists = await deezer_service.get_genre_artists(genre_id, limit=20)
            for artist_data in deezer_artists:
                artist_name = artist_data.get("name", "")
                if not artist_name or artist_name.lower() in seen_names:
                    continue
                seen_names.add(artist_name.lower())

                # Skip artists already in the library
                existing = await db.execute(
                    select(Artist).where(
                        func.lower(Artist.name) == artist_name.lower(),
                        Artist.in_library == True,
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                # Look up artist in DB (may have been searched before)
                db_artist_result = await db.execute(
                    select(Artist).where(
                        func.lower(Artist.name) == artist_name.lower()
                    )
                )
                db_artist = db_artist_result.scalar_one_or_none()

                confidence = _score_recommendation(
                    taste_profile,
                    artist_genres=db_artist.genres if db_artist else [genre],
                )

                rec = Recommendation(
                    recommendation_type="artist",
                    artist_id=db_artist.id if db_artist else None,
                    category="genre_explore",
                    reason=f"Based on your {', '.join(top_genres[:3])} taste",
                    reason_items=[f"Matches your preference for {genre}"],
                    confidence_score=round(confidence, 3),
                    relevance_score=0.7,
                    novelty_score=0.7,
                    score_factors={
                        "genre_match": round(confidence, 3),
                        "seed_genres": top_genres[:3],
                        "source": "deezer",
                    },
                    expires_at=datetime.utcnow() + timedelta(days=7),
                )
                recommendations.append(rec)

                if len(recommendations) >= 20:
                    break

            if len(recommendations) >= 20:
                break

    except Exception as e:
        logger.error(f"Error getting genre recommendations: {e}")

    return recommendations


async def _generate_deep_cuts_recommendations(db, taste_profile: Dict) -> List[Recommendation]:
    """Generate deep cuts - lesser-known albums from artists in library."""
    recommendations = []

    if not spotify_service.is_available:
        return recommendations

    from sqlalchemy import select
    result = await db.execute(
        select(Artist)
        .where(Artist.in_library == True)
        .where(Artist.spotify_id.isnot(None))
        .order_by(Artist.lastfm_playcount.desc().nullslast())
        .limit(15)
    )
    artists = result.scalars().all()

    for artist in artists:
        try:
            albums = await spotify_service.get_artist_albums(
                artist.spotify_id, album_type="album", limit=20
            )

            # Find albums not in library
            for album_data in albums:
                album_id = album_data.get("id")
                album_name = album_data.get("name", "")

                # Check if in library
                from sqlalchemy import func
                existing = await db.execute(
                    select(Album).where(
                        Album.artist_id == artist.id,
                        func.lower(Album.title) == album_name.lower(),
                        Album.in_library == True,
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                # Check if album exists in DB
                album_result = await db.execute(
                    select(Album).where(Album.spotify_id == album_id)
                )
                db_album = album_result.scalar_one_or_none()

                rec = Recommendation(
                    recommendation_type="album",
                    artist_id=artist.id,
                    album_id=db_album.id if db_album else None,
                    category="deep_cuts",
                    reason=f"More from {artist.name}",
                    reason_items=[f"You have {artist.name} in your library but may be missing this one"],
                    based_on_artist_id=artist.id,
                    confidence_score=0.75,
                    relevance_score=0.8,
                    novelty_score=0.6,
                    score_factors={"known_artist": 0.4, "missing_album": 0.35},
                    expires_at=datetime.utcnow() + timedelta(days=14),
                )
                recommendations.append(rec)

                # Limit deep cuts per artist
                if len([r for r in recommendations if r.based_on_artist_id == artist.id]) >= 2:
                    break

        except Exception as e:
            logger.error(f"Error getting deep cuts for {artist.name}: {e}")
            continue

    return recommendations[:20]  # Cap total deep cuts


async def _generate_mood_recommendations(db, taste_profile: Dict) -> List[Recommendation]:
    """Generate mood-based recommendations using Deezer keyword search.

    Spotify's /recommendations endpoint (which supported audio feature targeting)
    was deprecated in November 2024. We now use Deezer keyword search with
    mood-appropriate queries as a replacement.
    """
    recommendations = []

    # Mood → Deezer search query mapping
    mood_queries = {
        "energetic": "energetic dance workout",
        "chill": "chill ambient relax",
        "focus": "instrumental focus study",
        "happy": "happy upbeat feel good",
        "sad": "sad acoustic emotional",
        "workout": "workout cardio high energy",
    }

    moods_to_explore = ["energetic", "chill", "focus"]

    for mood_name in moods_to_explore:
        query = mood_queries.get(mood_name, mood_name)
        try:
            tracks = await deezer_service.search_tracks(query, limit=5)

            for track in tracks:
                artist = track.get("artist") or {}
                album = track.get("album") or {}
                if not artist.get("name"):
                    continue

                rec = Recommendation(
                    recommendation_type="track",
                    category="mood_based",
                    reason=f"{mood_name.capitalize()} mood",
                    reason_items=[f"Perfect for a {mood_name} mood"],
                    confidence_score=0.65,
                    relevance_score=0.6,
                    novelty_score=0.8,
                    score_factors={"mood": mood_name, "source": "deezer"},
                    expires_at=datetime.utcnow() + timedelta(days=3),
                )
                recommendations.append(rec)

        except Exception as e:
            logger.error(f"Error generating mood recommendations for {mood_name}: {e}")

    return recommendations


async def _generate_history_based_recommendations(
    db, taste_profile: Dict,
    artist_affinity: Dict[int, float] = None,
    genre_affinity: Dict[str, float] = None,
) -> List[Recommendation]:
    """Generate recommendations based on recent listening patterns with advanced scoring."""
    recommendations = []
    artist_affinity = artist_affinity or {}
    genre_affinity = genre_affinity or {}

    from sqlalchemy import select, func

    # Get most-played artists in the last 14 days
    since = datetime.utcnow() - timedelta(days=14)
    result = await db.execute(
        select(
            ListeningHistory.artist_id,
            func.count(ListeningHistory.id).label("play_count"),
        )
        .where(ListeningHistory.played_at >= since)
        .where(ListeningHistory.artist_id.isnot(None))
        .group_by(ListeningHistory.artist_id)
        .order_by(func.count(ListeningHistory.id).desc())
        .limit(5)
    )
    top_recent = result.all()

    if not top_recent:
        return recommendations

    feedback = await _get_category_feedback(db, "similar_artists")

    for artist_id, play_count in top_recent:
        artist_result = await db.execute(
            select(Artist).where(Artist.id == artist_id)
        )
        artist = artist_result.scalar_one_or_none()
        if not artist:
            continue

        # Get related artists from Spotify
        if artist.spotify_id and spotify_service.is_available:
            try:
                related = await spotify_service.get_related_artists(artist.spotify_id)
                for related_artist in related[:3]:
                    related_name = related_artist.get("name", "")

                    # Skip if in library
                    existing = await db.execute(
                        select(Artist).where(
                            func.lower(Artist.name) == related_name.lower(),
                            Artist.in_library == True,
                        )
                    )
                    if existing.scalar_one_or_none():
                        continue

                    # Find in DB
                    db_result = await db.execute(
                        select(Artist).where(
                            Artist.spotify_id == related_artist.get("id")
                        )
                    )
                    db_artist = db_result.scalar_one_or_none()

                    related_genres = related_artist.get("genres", [])
                    confidence, score_factors = score_recommendation_advanced(
                        taste_profile=taste_profile,
                        artist_affinity=artist_affinity,
                        genre_affinity=genre_affinity,
                        item_artist_id=db_artist.id if db_artist else None,
                        item_genres=related_genres,
                        based_on_artist_id=artist.id,
                        similarity_score=0.7,
                        feedback_history=feedback,
                    )
                    # Boost based on recency of listening
                    confidence = min(confidence + 0.1, 1.0)

                    rec = Recommendation(
                        recommendation_type="artist",
                        artist_id=db_artist.id if db_artist else None,
                        category="similar_artists",
                        reason=f"Because you've been listening to {artist.name}",
                        reason_items=[
                            f"You played {artist.name} {play_count} times recently",
                            f"Fans of {artist.name} also enjoy this artist",
                        ],
                        based_on_artist_id=artist.id,
                        confidence_score=round(confidence, 3),
                        relevance_score=0.8,
                        novelty_score=score_factors.get("novelty", 0.75),
                        score_factors=score_factors,
                        expires_at=datetime.utcnow() + timedelta(days=7),
                    )
                    recommendations.append(rec)

            except Exception as e:
                logger.error(f"Error getting related artists for {artist.name}: {e}")

    return recommendations


@celery_app.task(name="app.tasks.recommendations.check_new_releases")
def check_new_releases():
    """Check for new releases from library artists."""
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_check_new_releases_async())
    finally:
        loop.close()


async def _check_new_releases_async():
    """Async implementation of new release check."""
    logger.info("Checking for new releases")

    if not spotify_service.is_available:
        return {"status": "skipped", "reason": "Spotify not available"}

    new_releases_found = 0

    async with AsyncSessionLocal() as db:
        from sqlalchemy import select

        # Get library artists with Spotify IDs
        result = await db.execute(
            select(Artist)
            .where(Artist.in_library == True)
            .where(Artist.spotify_id.isnot(None))
        )
        artists = result.scalars().all()

        for artist in artists:
            try:
                albums = await spotify_service.get_artist_albums(
                    artist.spotify_id,
                    album_type="album,single,ep",
                    limit=10,
                )

                for album_data in albums:
                    release_date = album_data.get("release_date")
                    if not release_date:
                        continue

                    # Check if released in last 30 days
                    try:
                        from datetime import date
                        if len(release_date) == 4:
                            release_dt = date(int(release_date), 1, 1)
                        else:
                            release_dt = date.fromisoformat(release_date[:10])

                        if release_dt < date.today() - timedelta(days=30):
                            continue
                    except (ValueError, TypeError):
                        continue

                    # Check if already in library or already recommended
                    existing_album = await db.execute(
                        select(Album).where(
                            Album.spotify_id == album_data.get("id")
                        )
                    )
                    db_album = existing_album.scalar_one_or_none()
                    if db_album and db_album.in_library:
                        continue

                    # Check for existing recommendation
                    existing_rec = await db.execute(
                        select(Recommendation).where(
                            Recommendation.category == "release_radar",
                            Recommendation.based_on_artist_id == artist.id,
                            Recommendation.reason.ilike(f"%{album_data.get('name', '')}%"),
                        )
                    )
                    if existing_rec.scalar_one_or_none():
                        continue

                    album_name = album_data.get("name", "Unknown")
                    album_type = album_data.get("album_type", "album")
                    images = album_data.get("images", [])

                    rec = Recommendation(
                        recommendation_type="album",
                        artist_id=artist.id,
                        album_id=db_album.id if db_album else None,
                        category="release_radar",
                        reason=f"New {album_type} from {artist.name}: {album_name}",
                        reason_items=[
                            f"{artist.name} released a new {album_type}",
                            f"Released on {release_date}",
                        ],
                        based_on_artist_id=artist.id,
                        confidence_score=0.9,
                        relevance_score=0.9,
                        novelty_score=1.0,
                        score_factors={
                            "new_release": 0.5,
                            "in_library_artist": 0.4,
                            "release_type": album_type,
                        },
                        expires_at=datetime.utcnow() + timedelta(days=14),
                    )
                    db.add(rec)
                    new_releases_found += 1

            except Exception as e:
                logger.error(f"Error checking releases for {artist.name}: {e}")
                continue

        await db.commit()

    return {
        "status": "completed",
        "new_releases_found": new_releases_found,
    }


@celery_app.task(name="app.tasks.recommendations.update_taste_profile")
def update_taste_profile():
    """Update user taste profile based on listening history."""
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_update_taste_profile_async())
    finally:
        loop.close()


async def _update_taste_profile_async():
    """Async implementation of taste profile update."""
    logger.info("Updating taste profile")

    async with AsyncSessionLocal() as db:
        from sqlalchemy import select, func
        from collections import Counter

        # Analyze listening history (last 90 days)
        result = await db.execute(
            select(ListeningHistory)
            .where(ListeningHistory.played_at >= datetime.utcnow() - timedelta(days=90))
        )
        history = result.scalars().all()

        if not history:
            return {"status": "skipped", "reason": "No listening history"}

        # Calculate time patterns
        hours = [h.hour_of_day for h in history if h.hour_of_day is not None]
        days = [h.day_of_week for h in history if h.day_of_week is not None]

        hour_counts = Counter(hours)
        day_counts = Counter(days)

        peak_hours = [h for h, _ in hour_counts.most_common(3)]
        peak_days = [d for d, _ in day_counts.most_common(3)]

        # Get genre distribution from played artists
        all_genres = []
        artist_ids = set()
        album_ids = set()

        for entry in history:
            if entry.artist_id:
                artist_ids.add(entry.artist_id)
            if entry.album_id:
                album_ids.add(entry.album_id)

        if artist_ids:
            artist_result = await db.execute(
                select(Artist).where(Artist.id.in_(artist_ids))
            )
            artists = artist_result.scalars().all()
            for artist in artists:
                if artist.genres:
                    all_genres.extend(artist.genres)

        genre_counts = Counter(all_genres)
        total_genres = sum(genre_counts.values()) or 1
        genre_weights = {
            g: round(count / total_genres, 4)
            for g, count in genre_counts.most_common(20)
        }
        top_genres = list(genre_weights.keys())

        # Calculate decade preferences from albums
        decade_counts = Counter()
        if album_ids:
            album_result = await db.execute(
                select(Album.release_year)
                .where(Album.id.in_(album_ids))
                .where(Album.release_year.isnot(None))
            )
            for (year,) in album_result.all():
                if year:
                    decade = (year // 10) * 10
                    decade_counts[decade] += 1

        total_decades = sum(decade_counts.values()) or 1
        decade_weights = {
            str(d): round(c / total_decades, 4)
            for d, c in decade_counts.most_common(10)
        }
        preferred_decades = [int(d) for d in decade_weights.keys()]

        # Calculate audio feature averages from tracks
        track_ids = set(h.track_id for h in history if h.track_id)
        avg_features = {}
        if track_ids:
            feature_result = await db.execute(
                select(
                    func.avg(Track.danceability).label("avg_danceability"),
                    func.avg(Track.energy).label("avg_energy"),
                    func.avg(Track.valence).label("avg_valence"),
                    func.avg(Track.tempo).label("avg_tempo"),
                    func.avg(Track.acousticness).label("avg_acousticness"),
                    func.avg(Track.instrumentalness).label("avg_instrumentalness"),
                )
                .where(Track.id.in_(track_ids))
                .where(Track.danceability.isnot(None))
            )
            row = feature_result.one_or_none()
            if row:
                avg_features = {
                    "avg_danceability": round(float(row.avg_danceability or 0), 3),
                    "avg_energy": round(float(row.avg_energy or 0), 3),
                    "avg_valence": round(float(row.avg_valence or 0), 3),
                    "avg_tempo": round(float(row.avg_tempo or 0), 1),
                    "avg_acousticness": round(float(row.avg_acousticness or 0), 3),
                    "avg_instrumentalness": round(float(row.avg_instrumentalness or 0), 3),
                }

        # Calculate novelty preference
        # How often does the user listen to new artists vs. familiar ones?
        unique_artists = len(artist_ids)
        total_plays = len(history)
        novelty_preference = min(unique_artists / max(total_plays * 0.1, 1), 1.0)

        # Create or update taste profile
        result = await db.execute(
            select(TasteProfile).order_by(TasteProfile.version.desc()).limit(1)
        )
        profile = result.scalar_one_or_none()

        if profile:
            profile.version += 1
        else:
            profile = TasteProfile()
            db.add(profile)

        profile.top_genres = top_genres
        profile.genre_weights = genre_weights
        profile.preferred_decades = preferred_decades
        profile.decade_weights = decade_weights
        profile.peak_listening_hours = peak_hours
        profile.peak_listening_days = peak_days
        profile.total_plays = total_plays
        profile.total_artists = len(artist_ids)
        profile.total_albums = len(album_ids)
        profile.total_tracks = len(track_ids)
        profile.novelty_preference = round(novelty_preference, 3)
        profile.calculated_at = datetime.utcnow()

        # Apply audio feature averages
        if avg_features:
            profile.avg_danceability = avg_features.get("avg_danceability")
            profile.avg_energy = avg_features.get("avg_energy")
            profile.avg_valence = avg_features.get("avg_valence")
            profile.avg_tempo = avg_features.get("avg_tempo")
            profile.avg_acousticness = avg_features.get("avg_acousticness")
            profile.avg_instrumentalness = avg_features.get("avg_instrumentalness")

        # Store raw profile data
        profile.profile_data = {
            "genre_counts": dict(genre_counts.most_common(30)),
            "decade_counts": dict(decade_counts),
            "hour_counts": dict(hour_counts),
            "day_counts": dict(day_counts),
            "audio_features": avg_features,
        }

        await db.commit()

        return {
            "status": "completed",
            "plays_analyzed": total_plays,
            "top_genres": top_genres[:5],
            "preferred_decades": preferred_decades[:3],
            "novelty_preference": round(novelty_preference, 3),
            "audio_features": avg_features,
        }


async def _get_category_feedback(db, category: str) -> Dict:
    """Get aggregated feedback history for a recommendation category."""
    from sqlalchemy import select, func

    clicks_result = await db.execute(
        select(func.count(Recommendation.id))
        .where(Recommendation.category == category)
        .where(Recommendation.clicked == True)
    )
    dismissals_result = await db.execute(
        select(func.count(Recommendation.id))
        .where(Recommendation.category == category)
        .where(Recommendation.dismissed == True)
    )
    wishlisted_result = await db.execute(
        select(func.count(Recommendation.id))
        .where(Recommendation.category == category)
        .where(Recommendation.added_to_wishlist == True)
    )

    return {
        "clicks": clicks_result.scalar() or 0,
        "dismissals": dismissals_result.scalar() or 0,
        "wishlisted": wishlisted_result.scalar() or 0,
    }


@celery_app.task(name="app.tasks.recommendations.generate_discover_weekly")
def generate_discover_weekly():
    """Generate Discover Weekly style playlist."""
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_generate_discover_weekly_async())
    finally:
        loop.close()


async def _generate_discover_weekly_async():
    """Generate a personalized discovery playlist."""
    logger.info("Generating Discover Weekly")

    # This combines multiple recommendation strategies
    generate_daily_recommendations.delay()

    return {"status": "queued"}
