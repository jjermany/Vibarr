"""Advanced recommendation engine with collaborative filtering, time-decay, and diversity boosting."""

import logging
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import Counter, defaultdict

logger = logging.getLogger(__name__)


def time_decay_weight(played_at: datetime, half_life_days: float = 14.0) -> float:
    """Calculate exponential time-decay weight. More recent plays are weighted higher."""
    age_days = (datetime.utcnow() - played_at).total_seconds() / 86400
    return math.exp(-0.693 * age_days / half_life_days)


def build_artist_affinity_matrix(
    listening_history: List[dict],
    half_life_days: float = 14.0,
) -> Dict[int, float]:
    """Build a weighted artist affinity map from listening history with time-decay.

    Returns a dict of artist_id -> affinity_score (higher = more preferred).
    """
    affinity: Dict[int, float] = defaultdict(float)

    for entry in listening_history:
        artist_id = entry.get("artist_id")
        if not artist_id:
            continue

        played_at = entry.get("played_at")
        if not played_at:
            continue

        weight = time_decay_weight(played_at, half_life_days)

        # Boost for completion, penalize for skips
        completion = entry.get("completion_percentage", 100) or 100
        was_skipped = entry.get("was_skipped", False)

        if was_skipped:
            weight *= 0.3
        else:
            weight *= min(completion / 100.0, 1.0)

        affinity[artist_id] += weight

    # Normalize to 0-1 range
    if affinity:
        max_val = max(affinity.values())
        if max_val > 0:
            affinity = {k: v / max_val for k, v in affinity.items()}

    return dict(affinity)


def build_genre_affinity(
    listening_history: List[dict],
    artist_genres: Dict[int, List[str]],
    half_life_days: float = 21.0,
) -> Dict[str, float]:
    """Build genre affinity from listening history weighted by time-decay."""
    genre_scores: Dict[str, float] = defaultdict(float)

    for entry in listening_history:
        artist_id = entry.get("artist_id")
        if not artist_id:
            continue

        genres = artist_genres.get(artist_id, [])
        if not genres:
            continue

        played_at = entry.get("played_at")
        weight = time_decay_weight(played_at, half_life_days) if played_at else 0.5

        was_skipped = entry.get("was_skipped", False)
        if was_skipped:
            weight *= 0.3

        for genre in genres:
            genre_scores[genre] += weight

    # Normalize
    if genre_scores:
        max_val = max(genre_scores.values())
        if max_val > 0:
            genre_scores = {k: v / max_val for k, v in genre_scores.items()}

    return dict(genre_scores)


def score_recommendation_advanced(
    taste_profile: Dict,
    artist_affinity: Dict[int, float],
    genre_affinity: Dict[str, float],
    item_artist_id: Optional[int] = None,
    item_genres: Optional[List[str]] = None,
    item_audio_features: Optional[Dict[str, float]] = None,
    based_on_artist_id: Optional[int] = None,
    similarity_score: float = 0.5,
    feedback_history: Optional[Dict] = None,
) -> Tuple[float, Dict[str, float]]:
    """Advanced scoring combining multiple signals.

    Returns (final_score, score_factors_dict).
    """
    factors = {}
    weighted_sum = 0.0
    total_weight = 0.0

    # 1. Genre affinity matching (weight: 0.25)
    if item_genres and genre_affinity:
        genre_score = 0.0
        for genre in item_genres:
            genre_score += genre_affinity.get(genre, 0.0)
        genre_score = min(genre_score / max(len(item_genres), 1), 1.0)
        factors["genre_affinity"] = round(genre_score, 3)
        weighted_sum += genre_score * 0.25
        total_weight += 0.25

    # 2. Source artist affinity (weight: 0.20)
    if based_on_artist_id and artist_affinity:
        source_affinity = artist_affinity.get(based_on_artist_id, 0.0)
        factors["source_affinity"] = round(source_affinity, 3)
        weighted_sum += source_affinity * 0.20
        total_weight += 0.20

    # 3. External similarity score (weight: 0.20)
    factors["similarity"] = round(similarity_score, 3)
    weighted_sum += similarity_score * 0.20
    total_weight += 0.20

    # 4. Audio feature matching (weight: 0.15)
    if item_audio_features and taste_profile:
        feature_score = _audio_feature_similarity(taste_profile, item_audio_features)
        factors["audio_features"] = round(feature_score, 3)
        weighted_sum += feature_score * 0.15
        total_weight += 0.15

    # 5. Novelty adjustment (weight: 0.10)
    novelty_pref = taste_profile.get("novelty_preference", 0.5)
    is_known = item_artist_id and item_artist_id in artist_affinity
    if is_known:
        novelty_score = 0.3  # Lower novelty for known artists
    else:
        novelty_score = 0.8  # Higher novelty for unknown
    # Blend novelty preference with novelty score
    adjusted_novelty = novelty_score * novelty_pref + (1 - novelty_score) * (1 - novelty_pref)
    factors["novelty"] = round(adjusted_novelty, 3)
    weighted_sum += adjusted_novelty * 0.10
    total_weight += 0.10

    # 6. Feedback loop (weight: 0.10)
    if feedback_history:
        feedback_score = _feedback_adjustment(feedback_history)
        factors["feedback"] = round(feedback_score, 3)
        weighted_sum += feedback_score * 0.10
        total_weight += 0.10

    # Calculate final score
    if total_weight > 0:
        final_score = weighted_sum / total_weight
    else:
        final_score = 0.5

    final_score = max(0.0, min(1.0, final_score))
    return round(final_score, 3), factors


def diversify_recommendations(
    recommendations: List[dict],
    max_per_artist: int = 3,
    max_per_category: int = 15,
    genre_diversity_target: float = 0.6,
) -> List[dict]:
    """Apply diversity boosting to a list of recommendations.

    Ensures variety by:
    - Limiting recommendations per source artist
    - Balancing across categories
    - Boosting genre diversity
    """
    # Group by various dimensions
    by_artist: Dict[int, List[dict]] = defaultdict(list)
    by_category: Dict[str, List[dict]] = defaultdict(list)

    for rec in recommendations:
        artist_id = rec.get("based_on_artist_id") or rec.get("artist_id")
        if artist_id:
            by_artist[artist_id].append(rec)
        category = rec.get("category", "")
        by_category[category].append(rec)

    # Apply per-artist cap
    selected = set()
    for artist_id, recs in by_artist.items():
        sorted_recs = sorted(recs, key=lambda r: r.get("confidence_score", 0), reverse=True)
        for i, rec in enumerate(sorted_recs):
            if i < max_per_artist:
                selected.add(id(rec))

    # Apply per-category cap
    for category, recs in by_category.items():
        sorted_recs = sorted(recs, key=lambda r: r.get("confidence_score", 0), reverse=True)
        cat_selected = [r for r in sorted_recs if id(r) in selected]
        if len(cat_selected) > max_per_category:
            to_remove = cat_selected[max_per_category:]
            for r in to_remove:
                selected.discard(id(r))

    # Include recs that weren't grouped by artist (no artist_id)
    for rec in recommendations:
        artist_id = rec.get("based_on_artist_id") or rec.get("artist_id")
        if not artist_id:
            selected.add(id(rec))

    # Build final list preserving original order but filtered
    diversified = [r for r in recommendations if id(r) in selected]

    # Sort by confidence score descending
    diversified.sort(key=lambda r: r.get("confidence_score", 0), reverse=True)

    return diversified


def _audio_feature_similarity(taste_profile: Dict, item_features: Dict[str, float]) -> float:
    """Calculate similarity between taste profile audio features and item features."""
    features = ["danceability", "energy", "valence", "acousticness", "instrumentalness"]
    total_diff = 0.0
    count = 0

    for feature in features:
        profile_val = taste_profile.get(f"avg_{feature}")
        item_val = item_features.get(feature)
        if profile_val is not None and item_val is not None:
            total_diff += abs(profile_val - item_val)
            count += 1

    if count == 0:
        return 0.5  # Neutral when no features to compare

    avg_diff = total_diff / count
    # Convert difference to similarity (0 diff = 1.0 similarity)
    return max(0.0, 1.0 - avg_diff * 2.0)


def _feedback_adjustment(feedback_history: Dict) -> float:
    """Adjust score based on user feedback patterns for similar items."""
    clicks = feedback_history.get("clicks", 0)
    dismissals = feedback_history.get("dismissals", 0)
    wishlisted = feedback_history.get("wishlisted", 0)
    total = clicks + dismissals + wishlisted

    if total == 0:
        return 0.5  # Neutral

    positive = clicks + wishlisted * 2  # Wishlist counts double
    negative = dismissals
    ratio = positive / max(positive + negative, 1)
    return ratio


def calculate_listening_streak(play_dates: List[datetime]) -> dict:
    """Calculate listening streak from play dates.

    Returns current streak, longest streak, and streak data.
    """
    if not play_dates:
        return {"current_streak": 0, "longest_streak": 0, "streak_active": False}

    # Get unique dates
    unique_dates = sorted(set(d.date() for d in play_dates))

    # Calculate current streak
    today = datetime.utcnow().date()
    current_streak = 0
    check_date = today

    for date in reversed(unique_dates):
        if date == check_date:
            current_streak += 1
            check_date -= timedelta(days=1)
        elif date == check_date - timedelta(days=1):
            # Allow one day gap for "yesterday still counts"
            check_date = date
            current_streak += 1
            check_date -= timedelta(days=1)
        else:
            break

    # Calculate longest streak
    longest_streak = 1
    current_run = 1
    for i in range(1, len(unique_dates)):
        if (unique_dates[i] - unique_dates[i - 1]).days <= 1:
            current_run += 1
            longest_streak = max(longest_streak, current_run)
        else:
            current_run = 1

    if len(unique_dates) == 0:
        longest_streak = 0

    streak_active = current_streak > 0

    return {
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "streak_active": streak_active,
    }


def calculate_library_growth(
    items_with_dates: List[dict],
    days: int = 90,
) -> List[dict]:
    """Calculate cumulative library growth over time.

    items_with_dates should be a list of dicts with 'created_at' datetime.
    """
    if not items_with_dates:
        return []

    since = datetime.utcnow() - timedelta(days=days)
    daily_counts: Dict[str, int] = defaultdict(int)

    for item in items_with_dates:
        created_at = item.get("created_at")
        if created_at and created_at >= since:
            date_key = created_at.strftime("%Y-%m-%d")
            daily_counts[date_key] += 1

    # Build cumulative growth
    # Count items that existed before the period
    baseline = sum(
        1 for item in items_with_dates
        if item.get("created_at") and item["created_at"] < since
    )

    growth = []
    running_total = baseline
    current_date = since.date()
    end_date = datetime.utcnow().date()

    while current_date <= end_date:
        date_key = current_date.strftime("%Y-%m-%d")
        running_total += daily_counts.get(date_key, 0)
        growth.append({
            "date": date_key,
            "total": running_total,
            "added": daily_counts.get(date_key, 0),
        })
        current_date += timedelta(days=1)

    return growth
