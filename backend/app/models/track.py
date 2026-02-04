"""Track model."""

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Integer, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.album import Album


class Track(Base):
    """Track entity."""

    __tablename__ = "tracks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Basic info
    title: Mapped[str] = mapped_column(String(500), index=True)
    album_id: Mapped[int] = mapped_column(ForeignKey("albums.id"), index=True)

    # Track position
    disc_number: Mapped[Optional[int]] = mapped_column(Integer, default=1)
    track_number: Mapped[Optional[int]] = mapped_column(Integer)

    # External IDs
    musicbrainz_id: Mapped[Optional[str]] = mapped_column(String(36), unique=True, index=True)
    spotify_id: Mapped[Optional[str]] = mapped_column(String(50), unique=True, index=True)
    isrc: Mapped[Optional[str]] = mapped_column(String(20))

    # Duration
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)

    # Spotify audio features
    danceability: Mapped[Optional[float]] = mapped_column(Float)
    energy: Mapped[Optional[float]] = mapped_column(Float)
    key: Mapped[Optional[int]] = mapped_column(Integer)  # 0-11 pitch class
    loudness: Mapped[Optional[float]] = mapped_column(Float)  # dB
    mode: Mapped[Optional[int]] = mapped_column(Integer)  # 0=minor, 1=major
    speechiness: Mapped[Optional[float]] = mapped_column(Float)
    acousticness: Mapped[Optional[float]] = mapped_column(Float)
    instrumentalness: Mapped[Optional[float]] = mapped_column(Float)
    liveness: Mapped[Optional[float]] = mapped_column(Float)
    valence: Mapped[Optional[float]] = mapped_column(Float)
    tempo: Mapped[Optional[float]] = mapped_column(Float)  # BPM
    time_signature: Mapped[Optional[int]] = mapped_column(Integer)

    # Popularity
    spotify_popularity: Mapped[Optional[int]] = mapped_column(Integer)
    lastfm_playcount: Mapped[Optional[int]] = mapped_column(Integer)

    # Library status
    in_library: Mapped[bool] = mapped_column(Boolean, default=False)
    plex_rating_key: Mapped[Optional[str]] = mapped_column(String(50))

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    album: Mapped["Album"] = relationship("Album", back_populates="tracks", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Track(id={self.id}, title='{self.title}')>"
