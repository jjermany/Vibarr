"""Listening history model for tracking plays."""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ListeningHistory(Base):
    """Track user listening history for recommendations."""

    __tablename__ = "listening_history"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # What was listened to
    track_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tracks.id"), index=True)
    album_id: Mapped[Optional[int]] = mapped_column(ForeignKey("albums.id"), index=True)
    artist_id: Mapped[Optional[int]] = mapped_column(ForeignKey("artists.id"), index=True)

    # Plex identifiers (for items not yet in our DB)
    plex_track_key: Mapped[Optional[str]] = mapped_column(String(50))
    plex_album_key: Mapped[Optional[str]] = mapped_column(String(50))
    plex_artist_key: Mapped[Optional[str]] = mapped_column(String(50))

    # Play info
    played_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)  # How long they listened
    track_duration_ms: Mapped[Optional[int]] = mapped_column(Integer)  # Total track duration

    # Completion metrics
    completion_percentage: Mapped[Optional[float]] = mapped_column(Float)  # 0-100
    was_skipped: Mapped[bool] = mapped_column(Boolean, default=False)
    skip_time_ms: Mapped[Optional[int]] = mapped_column(Integer)  # When they skipped

    # Context
    source: Mapped[str] = mapped_column(String(50), default="plex")  # plex, manual
    device: Mapped[Optional[str]] = mapped_column(String(100))
    player: Mapped[Optional[str]] = mapped_column(String(100))

    # Time context (for time-based preferences)
    hour_of_day: Mapped[Optional[int]] = mapped_column(Integer)  # 0-23
    day_of_week: Mapped[Optional[int]] = mapped_column(Integer)  # 0-6

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<ListeningHistory(id={self.id}, track_id={self.track_id}, played_at={self.played_at})>"
