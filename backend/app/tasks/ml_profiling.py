"""ML-based taste profiling background tasks."""

import logging
from datetime import datetime, timedelta
from typing import Dict, List

from app.celery_app import celery_app
from app.database import AsyncSessionLocal
from app.services.ml_taste_profiler import (
    compute_taste_embedding,
    classify_taste_cluster,
    compute_taste_evolution,
    generate_taste_tags,
    TASTE_CLUSTERS,
)

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.ml_profiling.compute_ml_taste_profiles")
def compute_ml_taste_profiles():
    """Compute ML taste profiles for all users."""
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_compute_ml_taste_profiles_async())
    finally:
        loop.close()


async def _compute_ml_taste_profiles_async():
    """Async implementation of ML taste profile computation."""
    logger.info("Computing ML taste profiles for all users")

    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        from app.models.user import User
        from app.models.listening_history import ListeningHistory
        from app.models.track import Track
        from app.models.artist import Artist
        from app.models.user_preference import TasteProfile
        from app.services.advanced_recommendations import build_genre_affinity

        # Get all active users
        result = await db.execute(select(User).where(User.is_active == True))
        users = result.scalars().all()

        # If no users exist yet, compute a global profile
        if not users:
            users = [None]  # Sentinel for global profile

        profiles_computed = 0

        for user in users:
            try:
                user_id = user.id if user else None

                # Get listening history (last 180 days for ML profiling)
                since = datetime.utcnow() - timedelta(days=180)
                history_query = (
                    select(
                        ListeningHistory.track_id,
                        ListeningHistory.artist_id,
                        ListeningHistory.played_at,
                        ListeningHistory.completion_percentage,
                        ListeningHistory.was_skipped,
                    )
                    .where(ListeningHistory.played_at >= since)
                    .where(ListeningHistory.track_id.isnot(None))
                )
                history_result = await db.execute(history_query)
                history_rows = history_result.all()

                if not history_rows:
                    continue

                history_dicts = [
                    {
                        "track_id": row.track_id,
                        "artist_id": row.artist_id,
                        "played_at": row.played_at,
                        "completion_percentage": row.completion_percentage,
                        "was_skipped": row.was_skipped,
                    }
                    for row in history_rows
                ]

                # Get track audio features
                track_ids = set(h["track_id"] for h in history_dicts if h["track_id"])
                track_features = {}
                if track_ids:
                    track_result = await db.execute(
                        select(Track).where(
                            Track.id.in_(track_ids),
                            Track.danceability.isnot(None),
                        )
                    )
                    for track in track_result.scalars().all():
                        track_features[track.id] = {
                            "danceability": track.danceability,
                            "energy": track.energy,
                            "valence": track.valence,
                            "acousticness": track.acousticness,
                            "instrumentalness": track.instrumentalness,
                            "liveness": track.liveness,
                            "speechiness": track.speechiness,
                            "tempo": track.tempo,
                        }

                if not track_features:
                    continue

                # Compute taste embedding
                embedding = compute_taste_embedding(history_dicts, track_features)

                # Classify into taste cluster
                cluster_key, cluster_confidence = classify_taste_cluster(embedding)
                cluster_info = TASTE_CLUSTERS.get(cluster_key, {})

                # Build genre affinity for tags
                artist_ids = list(set(h["artist_id"] for h in history_dicts if h["artist_id"]))
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

                # Get decade weights from taste profile
                taste_profile_result = await db.execute(
                    select(TasteProfile).order_by(TasteProfile.version.desc()).limit(1)
                )
                taste_profile = taste_profile_result.scalar_one_or_none()
                decade_weights = taste_profile.decade_weights if taste_profile else {}

                # Generate taste tags
                tags = generate_taste_tags(embedding, genre_aff, decade_weights)

                # Update user record
                if user:
                    user.taste_cluster = cluster_key
                    user.taste_tags = tags
                    user.compatibility_vector = embedding

                # Update taste profile with ML data
                if taste_profile:
                    taste_profile.profile_data = {
                        **(taste_profile.profile_data or {}),
                        "ml_embedding": embedding,
                        "ml_cluster": cluster_key,
                        "ml_cluster_confidence": cluster_confidence,
                        "ml_cluster_label": cluster_info.get("label", ""),
                        "ml_tags": tags,
                    }

                profiles_computed += 1
                logger.info(
                    f"ML profile computed for user {user_id or 'global'}: "
                    f"cluster={cluster_key} ({cluster_confidence:.2f}), tags={tags}"
                )

            except Exception as e:
                logger.error(f"Error computing ML profile for user {user.id if user else 'global'}: {e}")
                continue

        await db.commit()

        return {
            "status": "completed",
            "profiles_computed": profiles_computed,
        }


@celery_app.task(name="app.tasks.ml_profiling.compute_taste_evolution_task")
def compute_taste_evolution_task():
    """Track taste evolution over time by storing periodic snapshots."""
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_compute_taste_evolution_async())
    finally:
        loop.close()


async def _compute_taste_evolution_async():
    """Store a taste embedding snapshot for evolution tracking."""
    logger.info("Computing taste evolution snapshot")

    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        from app.models.user_preference import TasteProfile

        result = await db.execute(
            select(TasteProfile).order_by(TasteProfile.version.desc()).limit(1)
        )
        profile = result.scalar_one_or_none()

        if not profile or not profile.profile_data:
            return {"status": "skipped", "reason": "No taste profile found"}

        embedding = profile.profile_data.get("ml_embedding", [])
        if not embedding:
            return {"status": "skipped", "reason": "No ML embedding in taste profile"}

        # Store snapshot in profile data
        evolution_history = profile.profile_data.get("evolution_history", [])
        period = datetime.utcnow().strftime("%Y-%m")

        # Don't duplicate the same period
        existing_periods = [e.get("period") for e in evolution_history]
        if period not in existing_periods:
            evolution_history.append({
                "period": period,
                "embedding": embedding,
                "sample_size": profile.total_plays,
            })

            # Keep last 12 months
            if len(evolution_history) > 12:
                evolution_history = evolution_history[-12:]

            profile.profile_data = {
                **profile.profile_data,
                "evolution_history": evolution_history,
            }

            # Compute evolution metrics
            if len(evolution_history) >= 2:
                evolution_data = compute_taste_evolution(evolution_history)
                profile.profile_data["evolution_metrics"] = evolution_data

            await db.commit()

            return {
                "status": "completed",
                "period": period,
                "periods_tracked": len(evolution_history),
            }

        return {"status": "skipped", "reason": f"Period {period} already recorded"}
