"""Social feature models - follows, shared playlists, activity feed."""

from datetime import datetime
from typing import Optional, List

from sqlalchemy import String, Integer, Float, DateTime, Boolean, ForeignKey, JSON, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserFollow(Base):
    """User follow relationships."""

    __tablename__ = "user_follows"
    __table_args__ = (
        UniqueConstraint("follower_id", "following_id", name="uq_user_follow"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    follower_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    following_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    follower = relationship("User", foreign_keys=[follower_id], back_populates="following")
    following = relationship("User", foreign_keys=[following_id], back_populates="followers")

    def __repr__(self) -> str:
        return f"<UserFollow(follower={self.follower_id}, following={self.following_id})>"


class SharedPlaylist(Base):
    """Shared playlists between users."""

    __tablename__ = "shared_playlists"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Playlist info
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(Text)
    cover_url: Mapped[Optional[str]] = mapped_column(String(500))
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)

    # Owner
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    # Collaborative settings
    collaborative: Mapped[bool] = mapped_column(Boolean, default=False)
    allowed_editors: Mapped[Optional[List[int]]] = mapped_column(JSON, default=list)

    # Stats
    total_tracks: Mapped[int] = mapped_column(Integer, default=0)
    total_duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    follower_count: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    items = relationship("SharedPlaylistItem", back_populates="playlist", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<SharedPlaylist(id={self.id}, name={self.name})>"


class SharedPlaylistItem(Base):
    """Items in a shared playlist."""

    __tablename__ = "shared_playlist_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    playlist_id: Mapped[int] = mapped_column(ForeignKey("shared_playlists.id"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)

    # Track reference
    track_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tracks.id"))
    album_id: Mapped[Optional[int]] = mapped_column(ForeignKey("albums.id"))
    artist_id: Mapped[Optional[int]] = mapped_column(ForeignKey("artists.id"))

    # Added by
    added_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    note: Mapped[Optional[str]] = mapped_column(String(500))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    playlist = relationship("SharedPlaylist", back_populates="items")

    def __repr__(self) -> str:
        return f"<SharedPlaylistItem(id={self.id}, playlist_id={self.playlist_id})>"


class ActivityFeed(Base):
    """Activity feed for social interactions."""

    __tablename__ = "activity_feed"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Who did the activity
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    # Activity type
    activity_type: Mapped[str] = mapped_column(String(50), index=True)
    # Types: listened, added_to_library, added_to_wishlist, created_playlist,
    #        added_to_playlist, followed_user, shared_recommendation, downloaded

    # What the activity is about
    artist_id: Mapped[Optional[int]] = mapped_column(ForeignKey("artists.id"))
    album_id: Mapped[Optional[int]] = mapped_column(ForeignKey("albums.id"))
    track_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tracks.id"))
    playlist_id: Mapped[Optional[int]] = mapped_column(ForeignKey("shared_playlists.id"))
    target_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))

    # Activity details
    message: Mapped[Optional[str]] = mapped_column(String(500))
    extra_data: Mapped[Optional[dict]] = mapped_column("extra_data", JSON, default=dict)

    # Visibility
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self) -> str:
        return f"<ActivityFeed(id={self.id}, user_id={self.user_id}, type={self.activity_type})>"
