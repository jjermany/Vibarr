"""Recommendation generation tasks."""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

from app.celery_app import celery_app
from app.database import AsyncSessionLocal
from app.services.spotify import spotify_service
from app.services.lastfm import lastfm_service
from app.models.artist import Artist
from app.models.album import Album
from app.models.recommendation import Recommendation
from app.models.listening_history import ListeningHistory
from app.models.user_preference import TasteProfile

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.recommendations.generate_daily_recommendations")
def generate_daily_recommendations():
    """Generate daily recommendation playlists."""
    import asyncio
    return asyncio.get_event_loop().run_until_complete(
        _generate_daily_recommendations_async()
    )


async def _generate_daily_recommendations_async():
    """Async implementation of daily recommendations."""
    logger.info("Generating daily recommendations")

    async with AsyncSessionLocal() as db:
        # Clear old recommendations
        from sqlalchemy import delete
        await db.execute(
            delete(Recommendation).where(
                Recommendation.expires_at < datetime.utcnow()
            )
        )
        await db.commit()

        recommendations_created = 0

        # Generate similar artist recommendations
        similar_recs = await _generate_similar_artist_recommendations(db)
        recommendations_created += len(similar_recs)

        # Generate genre-based recommendations
        genre_recs = await _generate_genre_recommendations(db)
        recommendations_created += len(genre_recs)

        # Save all recommendations
        for rec in similar_recs + genre_recs:
            db.add(rec)

        await db.commit()

        return {
            "status": "completed",
            "recommendations_created": recommendations_created,
        }


async def _generate_similar_artist_recommendations(db) -> List[Recommendation]:
    """Generate recommendations based on similar artists."""
    recommendations = []

    if not lastfm_service.is_available:
        return recommendations

    # Get top library artists
    from sqlalchemy import select, func
    result = await db.execute(
        select(Artist)
        .where(Artist.in_library == True)
        .order_by(Artist.lastfm_playcount.desc().nullslast())
        .limit(20)
    )
    top_artists = result.scalars().all()

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

                rec = Recommendation(
                    recommendation_type="artist",
                    artist_id=db_artist.id if db_artist else None,
                    category="similar_artists",
                    reason=f"Similar to {artist.name}",
                    reason_items=[f"Because you have {artist.name} in your library"],
                    based_on_artist_id=artist.id,
                    confidence_score=similar_artist.get("match", 0.5),
                    relevance_score=similar_artist.get("match", 0.5),
                    novelty_score=0.8,  # New artists are novel
                    expires_at=datetime.utcnow() + timedelta(days=7),
                )
                recommendations.append(rec)

        except Exception as e:
            logger.error(f"Error getting similar artists for {artist.name}: {e}")
            continue

    return recommendations


async def _generate_genre_recommendations(db) -> List[Recommendation]:
    """Generate recommendations based on genre preferences."""
    recommendations = []

    if not spotify_service.is_available:
        return recommendations

    # Get user's top genres from library
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

    if not all_genres:
        return recommendations

    # Count genre frequency
    from collections import Counter
    genre_counts = Counter(all_genres)
    top_genres = [g for g, _ in genre_counts.most_common(5)]

    # Get Spotify recommendations for top genres
    try:
        spotify_recs = await spotify_service.get_recommendations(
            seed_genres=top_genres[:5],
            limit=20,
        )

        for track in spotify_recs:
            artists = track.get("artists", [])
            if not artists:
                continue

            artist_name = artists[0].get("name")
            artist_spotify_id = artists[0].get("id")

            # Check if already in library
            from sqlalchemy import func
            existing = await db.execute(
                select(Artist).where(
                    func.lower(Artist.name) == artist_name.lower(),
                    Artist.in_library == True,
                )
            )
            if existing.scalar_one_or_none():
                continue

            # Find or reference artist
            artist_result = await db.execute(
                select(Artist).where(Artist.spotify_id == artist_spotify_id)
            )
            db_artist = artist_result.scalar_one_or_none()

            rec = Recommendation(
                recommendation_type="track",
                artist_id=db_artist.id if db_artist else None,
                category="genre_explore",
                reason=f"Based on your {', '.join(top_genres[:3])} taste",
                reason_items=[f"Matches your preference for {top_genres[0]}"],
                confidence_score=0.6,
                relevance_score=0.7,
                novelty_score=0.7,
                expires_at=datetime.utcnow() + timedelta(days=7),
            )
            recommendations.append(rec)

    except Exception as e:
        logger.error(f"Error getting genre recommendations: {e}")

    return recommendations


@celery_app.task(name="app.tasks.recommendations.check_new_releases")
def check_new_releases():
    """Check for new releases from library artists."""
    import asyncio
    return asyncio.get_event_loop().run_until_complete(
        _check_new_releases_async()
    )


async def _check_new_releases_async():
    """Async implementation of new release check."""
    logger.info("Checking for new releases")

    if not spotify_service.is_available:
        return {"status": "skipped", "reason": "Spotify not available"}

    new_releases_found = 0

    async with AsyncSessionLocal() as db:
        # Get library artists with Spotify IDs
        from sqlalchemy import select
        result = await db.execute(
            select(Artist)
            .where(Artist.in_library == True)
            .where(Artist.spotify_id.isnot(None))
        )
        artists = result.scalars().all()

        for artist in artists:
            try:
                # Get artist's albums from Spotify
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

                    # Check if already in library
                    existing = await db.execute(
                        select(Album).where(
                            Album.spotify_id == album_data.get("id")
                        )
                    )
                    if existing.scalar_one_or_none():
                        continue

                    # Create recommendation
                    rec = Recommendation(
                        recommendation_type="album",
                        artist_id=artist.id,
                        category="release_radar",
                        reason=f"New release from {artist.name}",
                        reason_items=[f"{artist.name} released a new album"],
                        based_on_artist_id=artist.id,
                        confidence_score=0.9,  # High confidence for followed artists
                        relevance_score=0.9,
                        novelty_score=1.0,
                        score_factors={"new_release": 0.5, "in_library_artist": 0.4},
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
    return asyncio.get_event_loop().run_until_complete(
        _update_taste_profile_async()
    )


async def _update_taste_profile_async():
    """Async implementation of taste profile update."""
    logger.info("Updating taste profile")

    async with AsyncSessionLocal() as db:
        from sqlalchemy import select, func
        from collections import Counter

        # Analyze listening history
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

        # Get genre distribution from played albums
        all_genres = []
        artist_ids = set()

        for entry in history:
            if entry.artist_id:
                artist_ids.add(entry.artist_id)

        if artist_ids:
            artist_result = await db.execute(
                select(Artist).where(Artist.id.in_(artist_ids))
            )
            artists = artist_result.scalars().all()
            for artist in artists:
                if artist.genres:
                    all_genres.extend(artist.genres)

        genre_counts = Counter(all_genres)
        total_genres = sum(genre_counts.values())
        genre_weights = {
            g: count / total_genres
            for g, count in genre_counts.most_common(20)
        }
        top_genres = list(genre_weights.keys())

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
        profile.peak_listening_hours = peak_hours
        profile.peak_listening_days = peak_days
        profile.total_plays = len(history)
        profile.total_artists = len(artist_ids)
        profile.calculated_at = datetime.utcnow()

        await db.commit()

        return {
            "status": "completed",
            "plays_analyzed": len(history),
            "top_genres": top_genres[:5],
        }


@celery_app.task(name="app.tasks.recommendations.generate_discover_weekly")
def generate_discover_weekly():
    """Generate Discover Weekly style playlist."""
    import asyncio
    return asyncio.get_event_loop().run_until_complete(
        _generate_discover_weekly_async()
    )


async def _generate_discover_weekly_async():
    """Generate a personalized discovery playlist."""
    logger.info("Generating Discover Weekly")

    # This combines multiple recommendation strategies
    generate_daily_recommendations.delay()

    return {"status": "queued"}
