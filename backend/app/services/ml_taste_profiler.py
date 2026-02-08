"""ML-based taste profiling service with clustering, embeddings, and predictive scoring."""

import logging
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import Counter, defaultdict

logger = logging.getLogger(__name__)

# Audio feature dimensions used for taste embedding
AUDIO_FEATURES = [
    "danceability", "energy", "valence", "acousticness",
    "instrumentalness", "liveness", "speechiness", "tempo",
]

# Predefined taste clusters with descriptive profiles
TASTE_CLUSTERS = {
    "energetic_explorer": {
        "label": "Energetic Explorer",
        "description": "Loves high-energy, danceable music across many genres",
        "centroid": {"energy": 0.8, "danceability": 0.75, "valence": 0.7, "acousticness": 0.15,
                     "instrumentalness": 0.1, "liveness": 0.3, "speechiness": 0.1, "tempo": 130},
    },
    "chill_curator": {
        "label": "Chill Curator",
        "description": "Gravitates toward relaxed, acoustic, and ambient sounds",
        "centroid": {"energy": 0.3, "danceability": 0.4, "valence": 0.5, "acousticness": 0.7,
                     "instrumentalness": 0.4, "liveness": 0.15, "speechiness": 0.05, "tempo": 95},
    },
    "eclectic_audiophile": {
        "label": "Eclectic Audiophile",
        "description": "Wide-ranging taste with appreciation for complexity and variety",
        "centroid": {"energy": 0.55, "danceability": 0.5, "valence": 0.5, "acousticness": 0.4,
                     "instrumentalness": 0.35, "liveness": 0.25, "speechiness": 0.08, "tempo": 115},
    },
    "rhythm_devotee": {
        "label": "Rhythm Devotee",
        "description": "Driven by strong beats, groove, and danceability",
        "centroid": {"energy": 0.7, "danceability": 0.85, "valence": 0.65, "acousticness": 0.1,
                     "instrumentalness": 0.05, "liveness": 0.2, "speechiness": 0.15, "tempo": 120},
    },
    "melancholy_romantic": {
        "label": "Melancholy Romantic",
        "description": "Drawn to emotional, introspective, and moody music",
        "centroid": {"energy": 0.35, "danceability": 0.35, "valence": 0.25, "acousticness": 0.55,
                     "instrumentalness": 0.2, "liveness": 0.15, "speechiness": 0.05, "tempo": 100},
    },
    "instrumental_voyager": {
        "label": "Instrumental Voyager",
        "description": "Prefers instrumental, ambient, and soundtrack-style music",
        "centroid": {"energy": 0.4, "danceability": 0.3, "valence": 0.4, "acousticness": 0.5,
                     "instrumentalness": 0.75, "liveness": 0.15, "speechiness": 0.03, "tempo": 105},
    },
    "indie_tastemaker": {
        "label": "Indie Tastemaker",
        "description": "Favors independent, alternative sounds with moderate energy",
        "centroid": {"energy": 0.55, "danceability": 0.5, "valence": 0.45, "acousticness": 0.35,
                     "instrumentalness": 0.15, "liveness": 0.2, "speechiness": 0.06, "tempo": 118},
    },
    "high_fidelity_purist": {
        "label": "High Fidelity Purist",
        "description": "Classic taste focused on well-produced, live, and organic recordings",
        "centroid": {"energy": 0.5, "danceability": 0.45, "valence": 0.5, "acousticness": 0.45,
                     "instrumentalness": 0.25, "liveness": 0.4, "speechiness": 0.05, "tempo": 110},
    },
}


def compute_taste_embedding(
    listening_history: List[dict],
    track_features: Dict[int, Dict[str, float]],
    half_life_days: float = 21.0,
) -> List[float]:
    """Compute a taste embedding vector from listening history and track audio features.

    The embedding is a weighted average of audio features from listened tracks,
    with time-decay weighting to emphasize recent taste.

    Returns a list of floats representing the taste in audio feature space.
    """
    weighted_sums = defaultdict(float)
    total_weight = 0.0

    for entry in listening_history:
        track_id = entry.get("track_id")
        if not track_id or track_id not in track_features:
            continue

        features = track_features[track_id]
        played_at = entry.get("played_at")
        if not played_at:
            continue

        # Time decay weight
        age_days = (datetime.utcnow() - played_at).total_seconds() / 86400
        weight = math.exp(-0.693 * age_days / half_life_days)

        # Adjust for completion
        completion = entry.get("completion_percentage", 100) or 100
        was_skipped = entry.get("was_skipped", False)

        if was_skipped:
            weight *= -0.2  # Negative weight for skips (repulse from these features)
        else:
            weight *= min(completion / 100.0, 1.0)

        for feature in AUDIO_FEATURES:
            val = features.get(feature)
            if val is not None:
                # Normalize tempo to 0-1 range (assume 60-200 BPM range)
                if feature == "tempo":
                    val = max(0.0, min(1.0, (val - 60) / 140))
                weighted_sums[feature] += val * weight
        total_weight += abs(weight)

    if total_weight == 0:
        return [0.5] * len(AUDIO_FEATURES)

    embedding = []
    for feature in AUDIO_FEATURES:
        val = weighted_sums.get(feature, 0) / total_weight
        embedding.append(round(max(0.0, min(1.0, val)), 4))

    return embedding


def classify_taste_cluster(embedding: List[float]) -> Tuple[str, float]:
    """Classify a taste embedding into the closest predefined cluster.

    Returns (cluster_key, confidence_score).
    """
    best_cluster = "eclectic_audiophile"
    best_distance = float("inf")

    for cluster_key, cluster_info in TASTE_CLUSTERS.items():
        centroid = cluster_info["centroid"]
        distance = 0.0
        for i, feature in enumerate(AUDIO_FEATURES):
            centroid_val = centroid.get(feature, 0.5)
            if feature == "tempo":
                centroid_val = max(0.0, min(1.0, (centroid_val - 60) / 140))
            embed_val = embedding[i] if i < len(embedding) else 0.5
            distance += (embed_val - centroid_val) ** 2

        distance = math.sqrt(distance)
        if distance < best_distance:
            best_distance = distance
            best_cluster = cluster_key

    # Convert distance to confidence (closer = higher confidence)
    max_possible_distance = math.sqrt(len(AUDIO_FEATURES))  # All features differ by 1.0
    confidence = max(0.0, 1.0 - (best_distance / max_possible_distance))

    return best_cluster, round(confidence, 3)


def compute_taste_evolution(
    historical_embeddings: List[dict],
) -> Dict:
    """Analyze how taste has evolved over time.

    historical_embeddings: list of {"period": "2026-01", "embedding": [...], "sample_size": N}

    Returns evolution metrics.
    """
    if len(historical_embeddings) < 2:
        return {
            "trend": "stable",
            "drift_rate": 0.0,
            "feature_changes": {},
            "periods_analyzed": len(historical_embeddings),
        }

    # Calculate drift between consecutive periods
    drifts = []
    feature_deltas = defaultdict(list)

    for i in range(1, len(historical_embeddings)):
        prev = historical_embeddings[i - 1]["embedding"]
        curr = historical_embeddings[i]["embedding"]

        period_drift = 0.0
        for j, feature in enumerate(AUDIO_FEATURES):
            prev_val = prev[j] if j < len(prev) else 0.5
            curr_val = curr[j] if j < len(curr) else 0.5
            delta = curr_val - prev_val
            feature_deltas[feature].append(delta)
            period_drift += delta ** 2

        drifts.append(math.sqrt(period_drift))

    avg_drift = sum(drifts) / len(drifts) if drifts else 0.0

    # Determine trend
    if avg_drift < 0.05:
        trend = "stable"
    elif avg_drift < 0.15:
        trend = "evolving"
    else:
        trend = "shifting"

    # Calculate net feature changes
    feature_changes = {}
    for feature, deltas in feature_deltas.items():
        net_change = sum(deltas)
        if abs(net_change) > 0.05:
            direction = "increasing" if net_change > 0 else "decreasing"
            feature_changes[feature] = {
                "direction": direction,
                "magnitude": round(abs(net_change), 3),
            }

    return {
        "trend": trend,
        "drift_rate": round(avg_drift, 3),
        "feature_changes": feature_changes,
        "periods_analyzed": len(historical_embeddings),
    }


def generate_taste_tags(
    embedding: List[float],
    genre_affinity: Dict[str, float],
    decade_weights: Dict[str, float],
) -> List[str]:
    """Generate human-readable taste tags from embedding and affinities.

    Returns a list of descriptive tags like "High Energy", "90s Nostalgia", etc.
    """
    tags = []

    # Audio feature-based tags
    feature_map = {i: f for i, f in enumerate(AUDIO_FEATURES)}

    for i, feature in enumerate(AUDIO_FEATURES):
        val = embedding[i] if i < len(embedding) else 0.5
        if feature == "energy":
            if val > 0.75:
                tags.append("High Energy")
            elif val < 0.3:
                tags.append("Low Key")
        elif feature == "danceability":
            if val > 0.75:
                tags.append("Dance Floor Ready")
            elif val < 0.3:
                tags.append("Contemplative")
        elif feature == "valence":
            if val > 0.7:
                tags.append("Feel Good")
            elif val < 0.3:
                tags.append("Dark & Moody")
        elif feature == "acousticness":
            if val > 0.65:
                tags.append("Acoustic Lover")
        elif feature == "instrumentalness":
            if val > 0.5:
                tags.append("Instrumental Fan")
        elif feature == "liveness":
            if val > 0.5:
                tags.append("Live Music Enthusiast")

    # Genre-based tags
    top_genres = sorted(genre_affinity.items(), key=lambda x: x[1], reverse=True)[:3]
    for genre, weight in top_genres:
        if weight > 0.15:
            tags.append(f"{genre.replace('-', ' ').title()} Aficionado")

    # Decade-based tags
    for decade_str, weight in decade_weights.items():
        if weight > 0.25:
            decade = int(decade_str) if decade_str.isdigit() else 0
            if decade >= 1960:
                tags.append(f"{decade}s Nostalgic")

    # Variety tags
    genre_count = len([g for g, w in genre_affinity.items() if w > 0.05])
    if genre_count > 10:
        tags.append("Genre Explorer")
    elif genre_count < 3:
        tags.append("Genre Specialist")

    return tags[:8]  # Cap at 8 tags


def compute_compatibility_score(
    embedding_a: List[float],
    embedding_b: List[float],
) -> Tuple[float, Dict[str, float]]:
    """Compute taste compatibility between two users based on their embeddings.

    Returns (compatibility_score, per_feature_similarity).
    """
    if not embedding_a or not embedding_b:
        return 0.5, {}

    per_feature = {}
    total_sim = 0.0
    count = 0

    for i, feature in enumerate(AUDIO_FEATURES):
        val_a = embedding_a[i] if i < len(embedding_a) else 0.5
        val_b = embedding_b[i] if i < len(embedding_b) else 0.5
        similarity = 1.0 - abs(val_a - val_b)
        per_feature[feature] = round(similarity, 3)
        total_sim += similarity
        count += 1

    overall = total_sim / count if count > 0 else 0.5
    return round(overall, 3), per_feature


def predict_item_score(
    user_embedding: List[float],
    item_features: Dict[str, float],
    genre_affinity: Dict[str, float],
    item_genres: List[str],
    novelty_preference: float = 0.5,
    is_known_artist: bool = False,
) -> Tuple[float, Dict[str, float]]:
    """Predict how much a user will enjoy an item based on ML taste profile.

    Combines embedding similarity, genre matching, and novelty adjustment.

    Returns (predicted_score, score_breakdown).
    """
    breakdown = {}

    # 1. Audio feature similarity (40% weight)
    feature_sim = 0.0
    feature_count = 0
    for i, feature in enumerate(AUDIO_FEATURES):
        user_val = user_embedding[i] if i < len(user_embedding) else 0.5
        item_val = item_features.get(feature)
        if item_val is not None:
            if feature == "tempo":
                item_val = max(0.0, min(1.0, (item_val - 60) / 140))
            feature_sim += 1.0 - abs(user_val - item_val)
            feature_count += 1

    audio_score = feature_sim / feature_count if feature_count > 0 else 0.5
    breakdown["audio_similarity"] = round(audio_score, 3)

    # 2. Genre affinity (35% weight)
    genre_score = 0.0
    if item_genres and genre_affinity:
        for genre in item_genres:
            genre_score += genre_affinity.get(genre, 0.0)
        genre_score = min(genre_score / max(len(item_genres), 1), 1.0)
    breakdown["genre_match"] = round(genre_score, 3)

    # 3. Novelty factor (15% weight)
    if is_known_artist:
        novelty_raw = 0.3
    else:
        novelty_raw = 0.8
    novelty_score = novelty_raw * novelty_preference + (1 - novelty_raw) * (1 - novelty_preference)
    breakdown["novelty"] = round(novelty_score, 3)

    # 4. Confidence penalty for sparse features (10% weight)
    data_quality = min(feature_count / len(AUDIO_FEATURES), 1.0)
    breakdown["data_quality"] = round(data_quality, 3)

    # Weighted combination
    final_score = (
        audio_score * 0.40
        + genre_score * 0.35
        + novelty_score * 0.15
        + data_quality * 0.10
    )

    return round(max(0.0, min(1.0, final_score)), 3), breakdown
