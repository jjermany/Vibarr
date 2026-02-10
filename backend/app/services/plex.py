"""Plex API integration for library access and listening history."""

from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

import httpx
from plexapi.server import PlexServer
from plexapi.myplex import MyPlexAccount
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


    async def verify_user_has_music_access(self, user_plex_token: str) -> Dict[str, Any]:
        """Verify a Plex user has shared access to the music library.

        Connects to the configured Plex server using the user's token and
        checks whether they can see the music library section. This works
        for both the server owner and users the library is shared with.

        Returns dict with 'allowed', 'username', 'email', 'plex_id', 'thumb'.
        """
        plex_url = cfg.get_optional("plex_url")
        if not plex_url:
            return {"allowed": False, "reason": "Plex server URL not configured"}

        try:
            # Get user account info from plex.tv
            account = MyPlexAccount(token=user_plex_token)
            user_info = {
                "username": account.username,
                "email": account.email,
                "plex_id": str(account.id),
                "thumb": account.thumb,
            }
        except Exception as e:
            logger.warning("Failed to get Plex account info: %s", e)
            return {"allowed": False, "reason": "Invalid Plex token"}

        try:
            # Try connecting to the server with the user's token
            user_server = PlexServer(plex_url, user_plex_token)
            # Check for a music library section
            for section in user_server.library.sections():
                if section.type == "artist":
                    return {"allowed": True, **user_info}

            return {"allowed": False, "reason": "No music library access", **user_info}
        except Exception as e:
            logger.warning("Plex user cannot access server: %s", e)
            return {"allowed": False, "reason": "No access to this Plex server", **user_info}

    @staticmethod
    async def create_plex_pin(client_id: str) -> Optional[Dict[str, Any]]:
        """Create a Plex PIN for the OAuth flow.

        Returns pin id, code, and the auth URL the frontend should open.
        """
        headers = {
            "Accept": "application/json",
            "X-Plex-Product": "Vibarr",
            "X-Plex-Client-Identifier": client_id,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://plex.tv/api/v2/pins",
                headers=headers,
                params={"strong": "true"},
            )
            if resp.status_code != 201:
                return None
            data = resp.json()
            return {
                "id": data["id"],
                "code": data["code"],
                "auth_url": (
                    f"https://app.plex.tv/auth#?clientID={client_id}"
                    f"&code={data['code']}"
                    f"&context%5Bdevice%5D%5Bproduct%5D=Vibarr"
                ),
            }

    @staticmethod
    async def check_plex_pin(pin_id: int, client_id: str) -> Optional[str]:
        """Check if a Plex PIN has been claimed. Returns the auth token or None."""
        headers = {
            "Accept": "application/json",
            "X-Plex-Client-Identifier": client_id,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://plex.tv/api/v2/pins/{pin_id}",
                headers=headers,
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            token = data.get("authToken")
            return token if token else None


# Singleton instance
plex_service = PlexService()
