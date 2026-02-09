"""Plex API integration for library access and listening history."""

from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

from plexapi.server import PlexServer
from plexapi.library import MusicSection
from plexapi.audio import Artist as PlexArtist, Album as PlexAlbum, Track as PlexTrack

from app.services import app_settings as cfg

logger = logging.getLogger(__name__)


class PlexService:
    """Plex API service for library access and listening history."""

    def __init__(self):
        """Initialize Plex client."""
        self._server: Optional[PlexServer] = None
        self._music_library: Optional[MusicSection] = None

    @property
    def server(self) -> Optional[PlexServer]:
        """Get or create Plex server connection."""
        plex_url = cfg.get_optional("plex_url")
        plex_token = cfg.get_optional("plex_token")
        if self._server is None and plex_url and plex_token:
            try:
                self._server = PlexServer(plex_url, plex_token)
            except Exception as e:
                logger.error(f"Failed to connect to Plex server: {e}")
        return self._server

    @property
    def music_library(self) -> Optional[MusicSection]:
        """Get music library section."""
        if self._music_library is None and self.server:
            try:
                for section in self.server.library.sections():
                    if section.type == "artist":
                        self._music_library = section
                        break
            except Exception as e:
                logger.error(f"Failed to get music library: {e}")
        return self._music_library

    @property
    def is_available(self) -> bool:
        """Check if Plex service is available."""
        return self.server is not None

    async def get_library_stats(self) -> Dict[str, Any]:
        """Get library statistics."""
        if not self.music_library:
            return {}

        try:
            return {
                "total_artists": self.music_library.totalSize,
                "total_albums": len(self.music_library.albums()),
                "total_tracks": len(self.music_library.searchTracks()),
            }
        except Exception as e:
            logger.error(f"Plex get library stats failed: {e}")
            return {}

    async def get_all_artists(self) -> List[Dict[str, Any]]:
        """Get all artists from library."""
        if not self.music_library:
            return []

        try:
            artists = self.music_library.all()
            return [self._serialize_artist(artist) for artist in artists]
        except Exception as e:
            logger.error(f"Plex get all artists failed: {e}")
            return []

    async def get_artist(self, rating_key: str) -> Optional[Dict[str, Any]]:
        """Get artist by rating key."""
        if not self.server:
            return None

        try:
            artist = self.server.fetchItem(int(rating_key))
            if isinstance(artist, PlexArtist):
                return self._serialize_artist(artist, include_albums=True)
        except Exception as e:
            logger.error(f"Plex get artist failed: {e}")
        return None

    async def get_artist_albums(self, rating_key: str) -> List[Dict[str, Any]]:
        """Get all albums for an artist."""
        if not self.server:
            return []

        try:
            artist = self.server.fetchItem(int(rating_key))
            if isinstance(artist, PlexArtist):
                return [self._serialize_album(album) for album in artist.albums()]
        except Exception as e:
            logger.error(f"Plex get artist albums failed: {e}")
        return []

    async def get_album(self, rating_key: str) -> Optional[Dict[str, Any]]:
        """Get album by rating key."""
        if not self.server:
            return None

        try:
            album = self.server.fetchItem(int(rating_key))
            if isinstance(album, PlexAlbum):
                return self._serialize_album(album, include_tracks=True)
        except Exception as e:
            logger.error(f"Plex get album failed: {e}")
        return None

    async def get_album_tracks(self, rating_key: str) -> List[Dict[str, Any]]:
        """Get all tracks for an album."""
        if not self.server:
            return []

        try:
            album = self.server.fetchItem(int(rating_key))
            if isinstance(album, PlexAlbum):
                return [self._serialize_track(track) for track in album.tracks()]
        except Exception as e:
            logger.error(f"Plex get album tracks failed: {e}")
        return []

    async def get_recently_added(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recently added albums."""
        if not self.music_library:
            return []

        try:
            albums = self.music_library.recentlyAdded(maxresults=limit)
            return [
                self._serialize_album(item)
                for item in albums
                if isinstance(item, PlexAlbum)
            ]
        except Exception as e:
            logger.error(f"Plex get recently added failed: {e}")
            return []

    async def get_recently_played(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recently played tracks."""
        if not self.music_library:
            return []

        try:
            # Get history from Plex
            history = self.server.history(maxresults=limit, librarySectionID=self.music_library.key)
            return [
                {
                    "track": self._serialize_track(item) if isinstance(item, PlexTrack) else None,
                    "viewed_at": item.viewedAt if hasattr(item, "viewedAt") else None,
                }
                for item in history
            ]
        except Exception as e:
            logger.error(f"Plex get recently played failed: {e}")
            return []

    async def get_listening_history(
        self,
        since: datetime = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Get detailed listening history."""
        if not self.server or not self.music_library:
            return []

        try:
            history = self.server.history(
                maxresults=limit,
                librarySectionID=self.music_library.key,
            )

            results = []
            for item in history:
                if isinstance(item, PlexTrack):
                    viewed_at = getattr(item, "viewedAt", None)
                    if since and viewed_at and viewed_at < since:
                        continue

                    results.append({
                        "track": self._serialize_track(item),
                        "played_at": viewed_at.isoformat() if viewed_at else None,
                        "rating_key": item.ratingKey,
                    })

            return results
        except Exception as e:
            logger.error(f"Plex get listening history failed: {e}")
            return []

    async def search(
        self,
        query: str,
        search_type: str = None,
        limit: int = 20,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Search library."""
        if not self.music_library:
            return {"artists": [], "albums": [], "tracks": []}

        try:
            results = {"artists": [], "albums": [], "tracks": []}

            if not search_type or search_type == "artist":
                artists = self.music_library.search(query, libtype="artist", limit=limit)
                results["artists"] = [self._serialize_artist(a) for a in artists]

            if not search_type or search_type == "album":
                albums = self.music_library.search(query, libtype="album", limit=limit)
                results["albums"] = [self._serialize_album(a) for a in albums]

            if not search_type or search_type == "track":
                tracks = self.music_library.search(query, libtype="track", limit=limit)
                results["tracks"] = [self._serialize_track(t) for t in tracks]

            return results
        except Exception as e:
            logger.error(f"Plex search failed: {e}")
            return {"artists": [], "albums": [], "tracks": []}

    async def refresh_library(self) -> bool:
        """Trigger library refresh/scan."""
        if not self.music_library:
            return False

        try:
            self.music_library.update()
            return True
        except Exception as e:
            logger.error(f"Plex refresh library failed: {e}")
            return False

    def _serialize_artist(
        self,
        artist: PlexArtist,
        include_albums: bool = False,
    ) -> Dict[str, Any]:
        """Serialize Plex artist to dict."""
        data = {
            "rating_key": str(artist.ratingKey),
            "name": artist.title,
            "sort_name": artist.titleSort,
            "thumb": artist.thumb,
            "art": artist.art,
            "genres": [g.tag for g in getattr(artist, "genres", [])],
            "country": [c.tag for c in getattr(artist, "countries", [])],
            "added_at": artist.addedAt.isoformat() if artist.addedAt else None,
            "updated_at": artist.updatedAt.isoformat() if artist.updatedAt else None,
        }

        if include_albums:
            data["albums"] = [self._serialize_album(a) for a in artist.albums()]

        return data

    def _serialize_album(
        self,
        album: PlexAlbum,
        include_tracks: bool = False,
    ) -> Dict[str, Any]:
        """Serialize Plex album to dict."""
        data = {
            "rating_key": str(album.ratingKey),
            "title": album.title,
            "artist_name": album.parentTitle,
            "artist_rating_key": str(album.parentRatingKey) if album.parentRatingKey else None,
            "year": album.year,
            "thumb": album.thumb,
            "genres": [g.tag for g in getattr(album, "genres", [])],
            "studio": album.studio,
            "added_at": album.addedAt.isoformat() if album.addedAt else None,
            "updated_at": album.updatedAt.isoformat() if album.updatedAt else None,
        }

        if include_tracks:
            data["tracks"] = [self._serialize_track(t) for t in album.tracks()]

        return data

    def _serialize_track(self, track: PlexTrack) -> Dict[str, Any]:
        """Serialize Plex track to dict."""
        return {
            "rating_key": str(track.ratingKey),
            "title": track.title,
            "artist_name": track.grandparentTitle,
            "album_name": track.parentTitle,
            "album_rating_key": str(track.parentRatingKey) if track.parentRatingKey else None,
            "track_number": track.trackNumber,
            "disc_number": track.parentIndex,
            "duration_ms": track.duration,
            "added_at": track.addedAt.isoformat() if track.addedAt else None,
            "view_count": track.viewCount,
            "last_viewed_at": track.lastViewedAt.isoformat() if track.lastViewedAt else None,
        }


# Singleton instance
plex_service = PlexService()
