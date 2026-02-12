"""Wishlist model for tracking wanted albums/artists."""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, Integer, Float, DateTime, Boolean, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column
import enum

from app.database import Base


class WishlistStatus(str, enum.Enum):
    """Wishlist item status."""
    WANTED = "wanted"
    SEARCHING = "searching"
    FOUND = "found"
    DOWNLOADING = "downloading"
    IMPORTING = "importing"
    DOWNLOADED = "downloaded"
    FAILED = "failed"


class WishlistPriority(str, enum.Enum):
    """Wishlist item priority."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class WishlistItem(Base):
    """Wishlist item for albums or artists user wants."""

    __tablename__ = "wishlist"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # What is wanted
    item_type: Mapped[str] = mapped_column(String(20), index=True)  # artist, album, track, playlist
    artist_id: Mapped[Optional[int]] = mapped_column(ForeignKey("artists.id"), index=True)
    album_id: Mapped[Optional[int]] = mapped_column(ForeignKey("albums.id"), index=True)

    # For items not yet in DB
    artist_name: Mapped[Optional[str]] = mapped_column(String(500))
    album_title: Mapped[Optional[str]] = mapped_column(String(500))
    musicbrainz_id: Mapped[Optional[str]] = mapped_column(String(36))
    spotify_id: Mapped[Optional[str]] = mapped_column(String(50))

    # Artwork (persisted from search results for items not yet in local DB)
    image_url: Mapped[Optional[str]] = mapped_column(String(1000))

    # Status
    status: Mapped[WishlistStatus] = mapped_column(
        SQLEnum(WishlistStatus),
        default=WishlistStatus.WANTED,
        index=True
    )
    priority: Mapped[WishlistPriority] = mapped_column(
        SQLEnum(WishlistPriority),
        default=WishlistPriority.NORMAL
    )

    # Source - how it was added
    source: Mapped[str] = mapped_column(String(50), default="manual")  # manual, recommendation, release_radar
    confidence_score: Mapped[Optional[float]] = mapped_column(Float)  # For auto-added items

    # Quality preferences
    preferred_format: Mapped[Optional[str]] = mapped_column(String(20))  # flac, 320, v0, any
    preferred_release_type: Mapped[Optional[str]] = mapped_column(String(50))  # studio, any

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Auto-download
    auto_download: Mapped[bool] = mapped_column(Boolean, default=False)

    # Search tracking
    last_searched_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    search_count: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<WishlistItem(id={self.id}, type={self.item_type}, status={self.status})>"
