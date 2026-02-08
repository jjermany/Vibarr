"""User model for multi-user support."""

from datetime import datetime
from typing import Optional, List

from sqlalchemy import String, Integer, Float, DateTime, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    """Application user for multi-user support."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Authentication
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)

    # Profile
    display_name: Mapped[Optional[str]] = mapped_column(String(100))
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500))
    bio: Mapped[Optional[str]] = mapped_column(String(500))

    # Plex integration (per-user)
    plex_token: Mapped[Optional[str]] = mapped_column(String(255))
    plex_username: Mapped[Optional[str]] = mapped_column(String(100))

    # Privacy settings
    profile_public: Mapped[bool] = mapped_column(Boolean, default=True)
    share_listening_activity: Mapped[bool] = mapped_column(Boolean, default=True)
    share_library: Mapped[bool] = mapped_column(Boolean, default=False)

    # Taste profile summary (cached from ML profiling)
    taste_cluster: Mapped[Optional[str]] = mapped_column(String(50))
    taste_tags: Mapped[Optional[List[str]]] = mapped_column(JSON, default=list)
    compatibility_vector: Mapped[Optional[List[float]]] = mapped_column(JSON, default=list)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Relationships
    followers = relationship("UserFollow", foreign_keys="UserFollow.following_id", back_populates="following")
    following = relationship("UserFollow", foreign_keys="UserFollow.follower_id", back_populates="follower")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username})>"
