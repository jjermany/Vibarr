"""Quality profile model for download format/quality preferences."""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, Integer, Float, DateTime, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class QualityProfile(Base):
    """Quality profile defining preferred formats and quality thresholds."""

    __tablename__ = "quality_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Whether this is the active/default profile
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    # Format preferences (ordered by priority)
    # e.g. ["flac", "320", "v0"] means prefer FLAC, then 320, then V0
    preferred_formats: Mapped[list] = mapped_column(JSON, default=list)

    # Minimum acceptable quality (reject anything below this)
    # Options: "any", "mp3", "192", "256", "v0", "320", "flac", "flac-24"
    min_quality: Mapped[str] = mapped_column(String(20), default="any")

    # Maximum file size per album in MB (0 = no limit)
    max_size_mb: Mapped[int] = mapped_column(Integer, default=0)

    # Minimum seeders required
    min_seeders: Mapped[int] = mapped_column(Integer, default=1)

    # Prefer releases with higher seeders
    prefer_well_seeded: Mapped[bool] = mapped_column(Boolean, default=True)

    # Release type preferences
    # e.g. ["album", "ep", "single"] or empty for any
    preferred_release_types: Mapped[list] = mapped_column(JSON, default=list)

    # Score boost for exact format match (0-50)
    format_match_weight: Mapped[float] = mapped_column(Float, default=30.0)

    # Score boost for seeders (0-20)
    seeder_weight: Mapped[float] = mapped_column(Float, default=15.0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<QualityProfile(id={self.id}, name='{self.name}', default={self.is_default})>"

    def score_release(self, quality: Optional[str], seeders: int, size_bytes: int) -> float:
        """Score a release against this profile's preferences."""
        score = 0.0

        # Format/quality scoring
        if quality and self.preferred_formats:
            if quality in self.preferred_formats:
                # Higher score for higher-priority format
                rank = self.preferred_formats.index(quality)
                format_score = self.format_match_weight * (1.0 - rank * 0.15)
                score += max(format_score, 0)
            elif quality == "flac-24" and "flac" in self.preferred_formats:
                # Hi-res FLAC matches FLAC preference
                score += self.format_match_weight

        # Minimum quality check
        if not self._meets_min_quality(quality):
            return -1.0  # Reject

        # Seeder scoring
        if seeders > 0:
            if seeders > 100:
                score += self.seeder_weight
            elif seeders > 50:
                score += self.seeder_weight * 0.8
            elif seeders > 20:
                score += self.seeder_weight * 0.6
            elif seeders > 5:
                score += self.seeder_weight * 0.4
            else:
                score += self.seeder_weight * 0.2

        # Size check
        if self.max_size_mb > 0 and size_bytes > 0:
            size_mb = size_bytes / (1024 * 1024)
            if size_mb > self.max_size_mb:
                return -1.0  # Reject

        return score

    def _meets_min_quality(self, quality: Optional[str]) -> bool:
        """Check if a quality level meets the minimum threshold."""
        if self.min_quality == "any" or not quality:
            return True

        quality_order = ["mp3", "192", "256", "v0", "320", "flac", "flac-24"]

        try:
            min_idx = quality_order.index(self.min_quality)
            quality_idx = quality_order.index(quality)
            return quality_idx >= min_idx
        except ValueError:
            return True  # Unknown quality, allow it


# Default profiles to seed the database
DEFAULT_PROFILES = [
    {
        "name": "Lossless",
        "description": "Prefer lossless FLAC, reject lossy formats",
        "preferred_formats": ["flac", "flac-24"],
        "min_quality": "flac",
        "min_seeders": 1,
        "is_default": False,
    },
    {
        "name": "High Quality",
        "description": "Prefer FLAC, accept 320kbps MP3 as fallback",
        "preferred_formats": ["flac", "320", "v0"],
        "min_quality": "v0",
        "min_seeders": 1,
        "is_default": True,
    },
    {
        "name": "Any Quality",
        "description": "Accept any quality, prefer better when available",
        "preferred_formats": ["flac", "320", "v0", "256", "192", "mp3"],
        "min_quality": "any",
        "min_seeders": 0,
        "is_default": False,
    },
]
