"""Database models."""

from app.models.artist import Artist
from app.models.album import Album
from app.models.track import Track
from app.models.listening_history import ListeningHistory
from app.models.wishlist import WishlistItem
from app.models.download import Download
from app.models.recommendation import Recommendation
from app.models.user_preference import UserPreference
from app.models.quality_profile import QualityProfile
from app.models.user import User
from app.models.social import UserFollow, SharedPlaylist, SharedPlaylistItem, ActivityFeed
from app.models.automation_rule import AutomationRule, AutomationLog
from app.models.app_settings import AppSettings

__all__ = [
    "Artist",
    "Album",
    "Track",
    "ListeningHistory",
    "WishlistItem",
    "Download",
    "Recommendation",
    "UserPreference",
    "QualityProfile",
    "User",
    "UserFollow",
    "SharedPlaylist",
    "SharedPlaylistItem",
    "ActivityFeed",
    "AutomationRule",
    "AutomationLog",
    "AppSettings",
]
