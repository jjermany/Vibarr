"""Last.fm API integration for similar artists and tags."""

from typing import Optional, List, Dict, Any
import logging

import pylast

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class LastFMService:
    """Last.fm API service for similar artists, tags, and scrobbling."""

    def __init__(self):
        """Initialize Last.fm client."""
        self._network: Optional[pylast.LastFMNetwork] = None

    @property
    def network(self) -> Optional[pylast.LastFMNetwork]:
        """Get or create Last.fm network."""
        if self._network is None and settings.lastfm_api_key:
            try:
                self._network = pylast.LastFMNetwork(
                    api_key=settings.lastfm_api_key,
                    api_secret=settings.lastfm_shared_secret,
                )
            except Exception as e:
                logger.error(f"Failed to initialize Last.fm network: {e}")
        return self._network

    @property
    def is_available(self) -> bool:
        """Check if Last.fm service is available."""
        return self.network is not None

    async def search_artists(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search for artists."""
        if not self.network:
            return []

        try:
            results = self.network.search_for_artist(query)
            artists = results.get_next_page()[:limit]
            return [
                {
                    "name": artist.name,
                    "url": artist.get_url(),
                    "listeners": artist.get_listener_count() if hasattr(artist, "get_listener_count") else None,
                }
                for artist in artists
            ]
        except Exception as e:
            logger.error(f"Last.fm artist search failed: {e}")
            return []

    async def get_artist_info(self, artist_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed artist info."""
        if not self.network:
            return None

        try:
            artist = self.network.get_artist(artist_name)
            return {
                "name": artist.name,
                "url": artist.get_url(),
                "bio": artist.get_bio_summary() if hasattr(artist, "get_bio_summary") else None,
                "listeners": artist.get_listener_count(),
                "playcount": artist.get_playcount(),
                "tags": [tag.item.name for tag in artist.get_top_tags(limit=10)],
            }
        except Exception as e:
            logger.error(f"Last.fm get artist info failed: {e}")
            return None

    async def get_similar_artists(
        self,
        artist_name: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get similar artists."""
        if not self.network:
            return []

        try:
            artist = self.network.get_artist(artist_name)
            similar = artist.get_similar(limit=limit)
            return [
                {
                    "name": item.item.name,
                    "match": item.match,  # Similarity score 0-1
                    "url": item.item.get_url(),
                }
                for item in similar
            ]
        except Exception as e:
            logger.error(f"Last.fm get similar artists failed: {e}")
            return []

    async def get_artist_top_albums(
        self,
        artist_name: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get artist's top albums by play count."""
        if not self.network:
            return []

        try:
            artist = self.network.get_artist(artist_name)
            albums = artist.get_top_albums(limit=limit)
            return [
                {
                    "title": item.item.title,
                    "playcount": item.weight,
                    "url": item.item.get_url(),
                }
                for item in albums
            ]
        except Exception as e:
            logger.error(f"Last.fm get artist top albums failed: {e}")
            return []

    async def get_artist_tags(self, artist_name: str, limit: int = 10) -> List[str]:
        """Get artist tags."""
        if not self.network:
            return []

        try:
            artist = self.network.get_artist(artist_name)
            tags = artist.get_top_tags(limit=limit)
            return [tag.item.name for tag in tags]
        except Exception as e:
            logger.error(f"Last.fm get artist tags failed: {e}")
            return []

    async def get_album_info(
        self,
        artist_name: str,
        album_title: str,
    ) -> Optional[Dict[str, Any]]:
        """Get album info."""
        if not self.network:
            return None

        try:
            album = self.network.get_album(artist_name, album_title)
            return {
                "title": album.title,
                "artist": album.artist.name,
                "url": album.get_url(),
                "playcount": album.get_playcount() if hasattr(album, "get_playcount") else None,
                "listeners": album.get_listener_count() if hasattr(album, "get_listener_count") else None,
                "tags": [tag.item.name for tag in album.get_top_tags(limit=10)],
            }
        except Exception as e:
            logger.error(f"Last.fm get album info failed: {e}")
            return None

    async def get_similar_tracks(
        self,
        artist_name: str,
        track_title: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get similar tracks."""
        if not self.network:
            return []

        try:
            track = self.network.get_track(artist_name, track_title)
            similar = track.get_similar(limit=limit)
            return [
                {
                    "title": item.item.title,
                    "artist": item.item.artist.name,
                    "match": item.match,
                    "url": item.item.get_url(),
                }
                for item in similar
            ]
        except Exception as e:
            logger.error(f"Last.fm get similar tracks failed: {e}")
            return []

    async def get_top_artists_by_tag(
        self,
        tag: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get top artists for a tag/genre."""
        if not self.network:
            return []

        try:
            tag_obj = self.network.get_tag(tag)
            artists = tag_obj.get_top_artists(limit=limit)
            return [
                {
                    "name": item.item.name,
                    "weight": item.weight,
                    "url": item.item.get_url(),
                }
                for item in artists
            ]
        except Exception as e:
            logger.error(f"Last.fm get top artists by tag failed: {e}")
            return []

    async def get_top_albums_by_tag(
        self,
        tag: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get top albums for a tag/genre."""
        if not self.network:
            return []

        try:
            tag_obj = self.network.get_tag(tag)
            albums = tag_obj.get_top_albums(limit=limit)
            return [
                {
                    "title": item.item.title,
                    "artist": item.item.artist.name,
                    "weight": item.weight,
                    "url": item.item.get_url(),
                }
                for item in albums
            ]
        except Exception as e:
            logger.error(f"Last.fm get top albums by tag failed: {e}")
            return []


# Singleton instance
lastfm_service = LastFMService()
