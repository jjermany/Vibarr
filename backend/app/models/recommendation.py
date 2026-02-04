"""Recommendation model for storing generated recommendations."""

from datetime import datetime
from typing import Optional, List

from sqlalchemy import String, Text, Integer, Float, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Recommendation(Base):
    """Generated recommendation for user."""

    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # What is being recommended
    recommendation_type: Mapped[str] = mapped_column(String(50), index=True)  # artist, album, track
    artist_id: Mapped[Optional[int]] = mapped_column(ForeignKey("artists.id"), index=True)
    album_id: Mapped[Optional[int]] = mapped_column(ForeignKey("albums.id"), index=True)
    track_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tracks.id"), index=True)

    # Recommendation category
    category: Mapped[str] = mapped_column(String(100), index=True)
    # Categories: discover_weekly, release_radar, similar_to_X, deep_cuts, genre_explore, etc.

    # Why recommended
    reason: Mapped[Optional[str]] = mapped_column(Text)
    reason_items: Mapped[Optional[List[str]]] = mapped_column(JSON, default=list)
    # e.g., ["Because you listened to Artist X", "Fans also like"]

    # Based on what (for similar-to recommendations)
    based_on_artist_id: Mapped[Optional[int]] = mapped_column(ForeignKey("artists.id"))
    based_on_album_id: Mapped[Optional[int]] = mapped_column(ForeignKey("albums.id"))

    # Scoring
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0, index=True)  # 0-1
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0)  # 0-1
    novelty_score: Mapped[float] = mapped_column(Float, default=0.0)  # 0-1 (how new/different)

    # Factors that contributed to score
    score_factors: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    # e.g., {"similar_artist": 0.3, "genre_match": 0.25, "audio_features": 0.2}

    # User interaction
    shown: Mapped[bool] = mapped_column(Boolean, default=False)
    shown_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    clicked: Mapped[bool] = mapped_column(Boolean, default=False)
    clicked_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    dismissed: Mapped[bool] = mapped_column(Boolean, default=False)
    dismissed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    added_to_wishlist: Mapped[bool] = mapped_column(Boolean, default=False)
    added_to_wishlist_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Playlist grouping (for Discover Weekly style playlists)
    playlist_id: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    playlist_position: Mapped[Optional[int]] = mapped_column(Integer)

    # Expiration
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Recommendation(id={self.id}, type={self.recommendation_type}, score={self.confidence_score})>"
