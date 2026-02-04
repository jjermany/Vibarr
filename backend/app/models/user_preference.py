"""User preference model for storing taste profile."""

from datetime import datetime
from typing import Optional, List, Dict

from sqlalchemy import String, Integer, Float, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserPreference(Base):
    """User taste profile and preferences."""

    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Preference type
    preference_type: Mapped[str] = mapped_column(String(50), index=True)
    # Types: genre, decade, mood, audio_feature, artist_affinity, time_preference

    # Genre preferences
    genre: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    genre_weight: Mapped[Optional[float]] = mapped_column(Float)  # -1 to 1 (dislike to like)

    # Decade preferences
    decade: Mapped[Optional[int]] = mapped_column(Integer)  # e.g., 1980, 1990, 2000
    decade_weight: Mapped[Optional[float]] = mapped_column(Float)

    # Audio feature preferences (ideal values)
    feature_name: Mapped[Optional[str]] = mapped_column(String(50))  # danceability, energy, etc.
    feature_value: Mapped[Optional[float]] = mapped_column(Float)  # preferred value
    feature_tolerance: Mapped[Optional[float]] = mapped_column(Float)  # acceptable range

    # Artist affinity (for collaborative filtering)
    artist_id: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    artist_affinity: Mapped[Optional[float]] = mapped_column(Float)  # Calculated from listens

    # Time-based preferences
    hour_range_start: Mapped[Optional[int]] = mapped_column(Integer)  # 0-23
    hour_range_end: Mapped[Optional[int]] = mapped_column(Integer)  # 0-23
    day_of_week: Mapped[Optional[int]] = mapped_column(Integer)  # 0-6

    # Aggregated preference data
    preference_data: Mapped[Optional[Dict]] = mapped_column(JSON, default=dict)

    # Confidence (how certain we are about this preference)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    sample_size: Mapped[int] = mapped_column(Integer, default=0)  # Number of data points

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<UserPreference(id={self.id}, type={self.preference_type})>"


class TasteProfile(Base):
    """Aggregated taste profile snapshot."""

    __tablename__ = "taste_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Profile version
    version: Mapped[int] = mapped_column(Integer, default=1)

    # Top genres (ordered by preference)
    top_genres: Mapped[List[str]] = mapped_column(JSON, default=list)
    genre_weights: Mapped[Dict[str, float]] = mapped_column(JSON, default=dict)

    # Decade preferences
    preferred_decades: Mapped[List[int]] = mapped_column(JSON, default=list)
    decade_weights: Mapped[Dict[str, float]] = mapped_column(JSON, default=dict)

    # Audio feature profile
    avg_danceability: Mapped[Optional[float]] = mapped_column(Float)
    avg_energy: Mapped[Optional[float]] = mapped_column(Float)
    avg_valence: Mapped[Optional[float]] = mapped_column(Float)
    avg_tempo: Mapped[Optional[float]] = mapped_column(Float)
    avg_acousticness: Mapped[Optional[float]] = mapped_column(Float)
    avg_instrumentalness: Mapped[Optional[float]] = mapped_column(Float)

    # Listening patterns
    total_plays: Mapped[int] = mapped_column(Integer, default=0)
    total_artists: Mapped[int] = mapped_column(Integer, default=0)
    total_albums: Mapped[int] = mapped_column(Integer, default=0)
    total_tracks: Mapped[int] = mapped_column(Integer, default=0)

    # Time patterns
    peak_listening_hours: Mapped[List[int]] = mapped_column(JSON, default=list)
    peak_listening_days: Mapped[List[int]] = mapped_column(JSON, default=list)

    # Adventure vs safety preference
    novelty_preference: Mapped[float] = mapped_column(Float, default=0.5)  # 0=safe, 1=adventurous

    # Raw data for analysis
    profile_data: Mapped[Dict] = mapped_column(JSON, default=dict)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    calculated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<TasteProfile(id={self.id}, version={self.version})>"
