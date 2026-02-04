"""Artist model."""

from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import String, Text, Integer, Float, DateTime, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.album import Album


class Artist(Base):
    """Artist entity."""

    __tablename__ = "artists"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Basic info
    name: Mapped[str] = mapped_column(String(500), index=True)
    sort_name: Mapped[Optional[str]] = mapped_column(String(500))
    disambiguation: Mapped[Optional[str]] = mapped_column(String(500))

    # External IDs
    musicbrainz_id: Mapped[Optional[str]] = mapped_column(String(36), unique=True, index=True)
    spotify_id: Mapped[Optional[str]] = mapped_column(String(50), unique=True, index=True)
    lastfm_url: Mapped[Optional[str]] = mapped_column(String(500))
    discogs_id: Mapped[Optional[str]] = mapped_column(String(50))

    # Metadata
    biography: Mapped[Optional[str]] = mapped_column(Text)
    country: Mapped[Optional[str]] = mapped_column(String(100))
    formed_year: Mapped[Optional[int]] = mapped_column(Integer)
    disbanded_year: Mapped[Optional[int]] = mapped_column(Integer)

    # Images
    image_url: Mapped[Optional[str]] = mapped_column(String(1000))
    thumb_url: Mapped[Optional[str]] = mapped_column(String(1000))
    banner_url: Mapped[Optional[str]] = mapped_column(String(1000))

    # Genres and tags
    genres: Mapped[Optional[List[str]]] = mapped_column(JSON, default=list)
    tags: Mapped[Optional[List[str]]] = mapped_column(JSON, default=list)

    # Spotify audio features (aggregated from tracks)
    avg_danceability: Mapped[Optional[float]] = mapped_column(Float)
    avg_energy: Mapped[Optional[float]] = mapped_column(Float)
    avg_valence: Mapped[Optional[float]] = mapped_column(Float)
    avg_tempo: Mapped[Optional[float]] = mapped_column(Float)

    # Popularity metrics
    spotify_popularity: Mapped[Optional[int]] = mapped_column(Integer)
    lastfm_listeners: Mapped[Optional[int]] = mapped_column(Integer)
    lastfm_playcount: Mapped[Optional[int]] = mapped_column(Integer)

    # Library status
    in_library: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    plex_rating_key: Mapped[Optional[str]] = mapped_column(String(50))

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    metadata_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Relationships
    albums: Mapped[List["Album"]] = relationship("Album", back_populates="artist", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Artist(id={self.id}, name='{self.name}')>"
