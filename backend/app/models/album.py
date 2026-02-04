"""Album model."""

from datetime import datetime, date
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import String, Text, Integer, Float, DateTime, Date, Boolean, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.artist import Artist
    from app.models.track import Track


class Album(Base):
    """Album entity."""

    __tablename__ = "albums"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Basic info
    title: Mapped[str] = mapped_column(String(500), index=True)
    artist_id: Mapped[int] = mapped_column(ForeignKey("artists.id"), index=True)

    # Album type
    album_type: Mapped[Optional[str]] = mapped_column(String(50))  # album, single, ep, compilation
    release_type: Mapped[Optional[str]] = mapped_column(String(50))  # studio, live, remix, soundtrack

    # External IDs
    musicbrainz_id: Mapped[Optional[str]] = mapped_column(String(36), unique=True, index=True)
    musicbrainz_release_group_id: Mapped[Optional[str]] = mapped_column(String(36))
    spotify_id: Mapped[Optional[str]] = mapped_column(String(50), unique=True, index=True)
    discogs_id: Mapped[Optional[str]] = mapped_column(String(50))
    discogs_master_id: Mapped[Optional[str]] = mapped_column(String(50))

    # Release info
    release_date: Mapped[Optional[date]] = mapped_column(Date, index=True)
    release_year: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    label: Mapped[Optional[str]] = mapped_column(String(500))
    catalog_number: Mapped[Optional[str]] = mapped_column(String(100))
    country: Mapped[Optional[str]] = mapped_column(String(100))

    # Track info
    total_tracks: Mapped[Optional[int]] = mapped_column(Integer)
    total_discs: Mapped[Optional[int]] = mapped_column(Integer)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)

    # Images
    cover_url: Mapped[Optional[str]] = mapped_column(String(1000))
    thumb_url: Mapped[Optional[str]] = mapped_column(String(1000))

    # Genres and tags
    genres: Mapped[Optional[List[str]]] = mapped_column(JSON, default=list)
    tags: Mapped[Optional[List[str]]] = mapped_column(JSON, default=list)

    # Spotify audio features (aggregated)
    avg_danceability: Mapped[Optional[float]] = mapped_column(Float)
    avg_energy: Mapped[Optional[float]] = mapped_column(Float)
    avg_valence: Mapped[Optional[float]] = mapped_column(Float)
    avg_tempo: Mapped[Optional[float]] = mapped_column(Float)
    avg_acousticness: Mapped[Optional[float]] = mapped_column(Float)
    avg_instrumentalness: Mapped[Optional[float]] = mapped_column(Float)

    # Popularity and ratings
    spotify_popularity: Mapped[Optional[int]] = mapped_column(Integer)
    lastfm_playcount: Mapped[Optional[int]] = mapped_column(Integer)
    user_rating: Mapped[Optional[float]] = mapped_column(Float)  # User's personal rating
    critic_rating: Mapped[Optional[float]] = mapped_column(Float)  # From review aggregators

    # Description/review
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Library status
    in_library: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    plex_rating_key: Mapped[Optional[str]] = mapped_column(String(50))
    library_path: Mapped[Optional[str]] = mapped_column(String(1000))

    # Quality info for library items
    format: Mapped[Optional[str]] = mapped_column(String(20))  # flac, mp3, etc.
    bitrate: Mapped[Optional[int]] = mapped_column(Integer)
    sample_rate: Mapped[Optional[int]] = mapped_column(Integer)
    bit_depth: Mapped[Optional[int]] = mapped_column(Integer)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    metadata_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    added_to_library_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Relationships
    artist: Mapped["Artist"] = relationship("Artist", back_populates="albums", lazy="selectin")
    tracks: Mapped[List["Track"]] = relationship("Track", back_populates="album", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Album(id={self.id}, title='{self.title}')>"
