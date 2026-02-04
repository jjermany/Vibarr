"""Download model for tracking download queue and history."""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, Integer, Float, DateTime, Boolean, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column
import enum

from app.database import Base


class DownloadStatus(str, enum.Enum):
    """Download status."""
    PENDING = "pending"
    SEARCHING = "searching"
    FOUND = "found"
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    IMPORTING = "importing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Download(Base):
    """Download queue and history."""

    __tablename__ = "downloads"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # What is being downloaded
    album_id: Mapped[Optional[int]] = mapped_column(ForeignKey("albums.id"), index=True)
    wishlist_id: Mapped[Optional[int]] = mapped_column(ForeignKey("wishlist.id"), index=True)

    # Basic info (for display before album is in DB)
    artist_name: Mapped[str] = mapped_column(String(500))
    album_title: Mapped[str] = mapped_column(String(500))

    # Status
    status: Mapped[DownloadStatus] = mapped_column(
        SQLEnum(DownloadStatus),
        default=DownloadStatus.PENDING,
        index=True
    )
    status_message: Mapped[Optional[str]] = mapped_column(Text)

    # Search info
    search_query: Mapped[Optional[str]] = mapped_column(String(1000))
    indexer_name: Mapped[Optional[str]] = mapped_column(String(100))
    indexer_id: Mapped[Optional[str]] = mapped_column(String(100))

    # Release info
    release_title: Mapped[Optional[str]] = mapped_column(String(1000))
    release_size: Mapped[Optional[int]] = mapped_column(Integer)  # bytes
    release_format: Mapped[Optional[str]] = mapped_column(String(50))
    release_quality: Mapped[Optional[str]] = mapped_column(String(50))
    seeders: Mapped[Optional[int]] = mapped_column(Integer)
    leechers: Mapped[Optional[int]] = mapped_column(Integer)

    # Download client info
    download_client: Mapped[Optional[str]] = mapped_column(String(50))  # qbittorrent, etc.
    download_id: Mapped[Optional[str]] = mapped_column(String(100))  # torrent hash or similar
    download_path: Mapped[Optional[str]] = mapped_column(String(1000))

    # Progress
    progress: Mapped[float] = mapped_column(Float, default=0.0)  # 0-100
    download_speed: Mapped[Optional[int]] = mapped_column(Integer)  # bytes/sec
    eta_seconds: Mapped[Optional[int]] = mapped_column(Integer)

    # Beets import
    beets_imported: Mapped[bool] = mapped_column(Boolean, default=False)
    final_path: Mapped[Optional[str]] = mapped_column(String(1000))

    # Source tracking
    source: Mapped[str] = mapped_column(String(50), default="manual")  # manual, auto, wishlist

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    def __repr__(self) -> str:
        return f"<Download(id={self.id}, album='{self.album_title}', status={self.status})>"
