"""Last.fm API integration for similar artists and tags."""

import asyncio
from typing import Optional, List, Dict, Any
import logging

import pylast

from app.services import app_settings as cfg

logger = logging.getLogger(__name__)


class LastFMService:
    """Last.fm API service for similar artists, tags, and scrobbling."""

    def __init__(self):
        """Initialize Last.fm client."""
        self._network: Optional[pylast.LastFMNetwork] = None

    @property
    def network(self) -> Optional[pylast.LastFMNetwork]:
        """Get or create Last.fm network."""
        api_key = cfg.get_optional("lastfm_api_key")
        if self._network is None and api_key:
            try:
                self._network = pylast.LastFMNetwork(
                    api_key=api_key,
                    api_secret=cfg.get_setting("lastfm_shared_secret"),
                )
            except Exception as e:
                logger.error(f"Failed to initialize Last.fm network: {e}")
        return self._network

    @property
    def is_available(self) -> bool:
        """Check if Last.fm service is available."""
        return self.network is not None

    def _get_artist_image(self, artist: pylast.Artist) -> Optional[str]:
        """Get artist image URL, trying cover image then top album fallback."""
        try:
            cover = artist.get_cover_image()
            if cover:
                return cover
        except Exception:
            pass
        # Fallback: use the top album's cover art
        try:
            top_albums = artist.get_top_albums(limit=1)
            if top_albums:
                album_cover = top_albums[0].item.get_cover_image()
                if album_cover:
                    return album_cover
        except Exception:
            pass
        return None

    def _get_album_image(self, album: pylast.Album) -> Optional[str]:
        """Get album cover image URL."""
        try:
            cover = album.get_cover_image()
            if cover:
                return cover
        except Exception:
            pass
        return None

    def _fetch_artists(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Blocking: search for artists via pylast."""
        results = self.network.search_for_artist(query)
        artists = results.get_next_page()[:limit]
        artist_results = []
        for artist in artists:
            image_url = self._get_artist_image(artist)
            listeners = None
            try:
                listeners = artist.get_listener_count()
            except Exception:
                pass
            artist_results.append({
                "name": artist.name,
                "url": artist.get_url(),
                "image_url": image_url,
                "listeners": listeners,
            })
        return artist_results

    async def search_artists(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search for artists."""
        if not self.network:
            return []

        try:
            return await asyncio.to_thread(self._fetch_artists, query, limit)
        except Exception as e:
            logger.error(f"Last.fm artist search failed: {e}")
            return []

    def _fetch_albums(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Blocking: search for albums via pylast."""
        results = self.network.search_for_album(query)
        albums = results.get_next_page()[:limit]
        album_results = []
        for album in albums:
            image_url = self._get_album_image(album)
            album_results.append({
                "title": album.title,
                "artist": album.artist.name if album.artist else None,
                "url": album.get_url(),
                "image_url": image_url,
            })
        return album_results

    async def search_albums(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search for albums."""
        if not self.network:
            return []

        try:
            return await asyncio.to_thread(self._fetch_albums, query, limit)
        except Exception as e:
            logger.error(f"Last.fm album search failed: {e}")
            return []

    def _fetch_tracks(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Blocking: search for tracks via pylast."""
        results = self.network.search_for_track("", query)
        tracks = results.get_next_page()[:limit]
        track_results = []
        for track in tracks:
            image_url = None
            try:
                album = track.get_album()
                if album:
                    image_url = self._get_album_image(album)
            except Exception:
                pass
            track_results.append({
                "title": track.title,
                "artist": track.artist.name if track.artist else None,
                "url": track.get_url(),
                "image_url": image_url,
            })
        return track_results

    async def search_tracks(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search for tracks."""
        if not self.network:
            return []

        try:
            return await asyncio.to_thread(self._fetch_tracks, query, limit)
        except Exception as e:
            logger.error(f"Last.fm track search failed: {e}")
            return []

    def _fetch_artist_info(self, artist_name: str) -> Optional[Dict[str, Any]]:
        """Blocking: fetch detailed artist info via pylast."""
        artist = self.network.get_artist(artist_name)
        image_url = self._get_artist_image(artist)
        bio = None
        try:
            bio = artist.get_bio_summary()
        except Exception:
            pass
        return {
            "name": artist.name,
            "url": artist.get_url(),
            "image_url": image_url,
            "bio": bio,
            "listeners": artist.get_listener_count(),
            "playcount": artist.get_playcount(),
            "tags": [tag.item.name for tag in artist.get_top_tags(limit=10)],
        }

    async def get_artist_info(self, artist_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed artist info."""
        if not self.network:
            return None

        try:
            return await asyncio.to_thread(self._fetch_artist_info, artist_name)
        except Exception as e:
            logger.error(f"Last.fm get artist info failed: {e}")
            return None

    def _fetch_artist_preview(self, artist_name: str) -> Optional[Dict[str, Any]]:
        """Blocking: fetch comprehensive artist preview via pylast."""
        artist = self.network.get_artist(artist_name)
        image_url = self._get_artist_image(artist)
        bio = None
        try:
            bio = artist.get_bio_summary()
        except Exception:
            pass

        top_albums = []
        try:
            albums = artist.get_top_albums(limit=6)
            for item in albums:
                album_image = self._get_album_image(item.item)
                top_albums.append({
                    "title": item.item.title,
                    "playcount": item.weight,
                    "image_url": album_image,
                })
        except Exception:
            pass

        tags = []
        try:
            tags = [tag.item.name for tag in artist.get_top_tags(limit=10)]
        except Exception:
            pass

        listeners = None
        playcount = None
        try:
            listeners = artist.get_listener_count()
            playcount = artist.get_playcount()
        except Exception:
            pass

        return {
            "name": artist.name,
            "url": artist.get_url(),
            "image_url": image_url,
            "bio": bio,
            "listeners": listeners,
            "playcount": playcount,
            "tags": tags,
            "top_albums": top_albums,
        }

    async def get_artist_preview(self, artist_name: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive artist preview data for the UI."""
        if not self.network:
            return None

        try:
            return await asyncio.to_thread(self._fetch_artist_preview, artist_name)
        except Exception as e:
            logger.error(f"Last.fm get artist preview failed: {e}")
            return None

    def _fetch_album_preview(self, artist_name: str, album_title: str) -> Optional[Dict[str, Any]]:
        """Blocking: fetch comprehensive album preview via pylast."""
        album = self.network.get_album(artist_name, album_title)
        image_url = self._get_album_image(album)

        tracks = []
        try:
            for track in album.get_tracks():
                tracks.append({
                    "title": track.title,
                    "duration": track.get_duration() if hasattr(track, "get_duration") else None,
                })
        except Exception:
            pass

        tags = []
        try:
            tags = [tag.item.name for tag in album.get_top_tags(limit=10)]
        except Exception:
            pass

        listeners = None
        playcount = None
        try:
            listeners = album.get_listener_count()
            playcount = album.get_playcount()
        except Exception:
            pass

        return {
            "title": album.title,
            "artist": artist_name,
            "url": album.get_url(),
            "image_url": image_url,
            "listeners": listeners,
            "playcount": playcount,
            "tags": tags,
            "tracks": tracks,
        }

    async def get_album_preview(self, artist_name: str, album_title: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive album preview data for the UI."""
        if not self.network:
            return None

        try:
            return await asyncio.to_thread(self._fetch_album_preview, artist_name, album_title)
        except Exception as e:
            logger.error(f"Last.fm get album preview failed: {e}")
            return None

    def _fetch_similar_artists(self, artist_name: str, limit: int) -> List[Dict[str, Any]]:
        """Blocking: fetch similar artists via pylast."""
        artist = self.network.get_artist(artist_name)
        similar = artist.get_similar(limit=limit)
        return [
            {
                "name": item.item.name,
                "match": item.match,
                "url": item.item.get_url(),
            }
            for item in similar
        ]

    async def get_similar_artists(
        self,
        artist_name: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get similar artists."""
        if not self.network:
            return []

        try:
            return await asyncio.to_thread(self._fetch_similar_artists, artist_name, limit)
        except Exception as e:
            logger.error(f"Last.fm get similar artists failed: {e}")
            return []

    def _fetch_artist_top_albums(self, artist_name: str, limit: int) -> List[Dict[str, Any]]:
        """Blocking: fetch artist top albums via pylast."""
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

    async def get_artist_top_albums(
        self,
        artist_name: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get artist's top albums by play count."""
        if not self.network:
            return []

        try:
            return await asyncio.to_thread(self._fetch_artist_top_albums, artist_name, limit)
        except Exception as e:
            logger.error(f"Last.fm get artist top albums failed: {e}")
            return []

    def _fetch_artist_tags(self, artist_name: str, limit: int) -> List[str]:
        """Blocking: fetch artist tags via pylast."""
        artist = self.network.get_artist(artist_name)
        tags = artist.get_top_tags(limit=limit)
        return [tag.item.name for tag in tags]

    async def get_artist_tags(self, artist_name: str, limit: int = 10) -> List[str]:
        """Get artist tags."""
        if not self.network:
            return []

        try:
            return await asyncio.to_thread(self._fetch_artist_tags, artist_name, limit)
        except Exception as e:
            logger.error(f"Last.fm get artist tags failed: {e}")
            return []

    def _fetch_album_info(self, artist_name: str, album_title: str) -> Optional[Dict[str, Any]]:
        """Blocking: fetch album info via pylast."""
        album = self.network.get_album(artist_name, album_title)
        return {
            "title": album.title,
            "artist": album.artist.name,
            "url": album.get_url(),
            "playcount": album.get_playcount() if hasattr(album, "get_playcount") else None,
            "listeners": album.get_listener_count() if hasattr(album, "get_listener_count") else None,
            "tags": [tag.item.name for tag in album.get_top_tags(limit=10)],
        }

    async def get_album_info(
        self,
        artist_name: str,
        album_title: str,
    ) -> Optional[Dict[str, Any]]:
        """Get album info."""
        if not self.network:
            return None

        try:
            return await asyncio.to_thread(self._fetch_album_info, artist_name, album_title)
        except Exception as e:
            logger.error(f"Last.fm get album info failed: {e}")
            return None

    def _fetch_similar_tracks(self, artist_name: str, track_title: str, limit: int) -> List[Dict[str, Any]]:
        """Blocking: fetch similar tracks via pylast."""
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
            return await asyncio.to_thread(self._fetch_similar_tracks, artist_name, track_title, limit)
        except Exception as e:
            logger.error(f"Last.fm get similar tracks failed: {e}")
            return []

    def _fetch_top_artists_by_tag(self, tag: str, limit: int) -> List[Dict[str, Any]]:
        """Blocking: fetch top artists for a tag via pylast."""
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

    async def get_top_artists_by_tag(
        self,
        tag: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get top artists for a tag/genre."""
        if not self.network:
            return []

        try:
            return await asyncio.to_thread(self._fetch_top_artists_by_tag, tag, limit)
        except Exception as e:
            logger.error(f"Last.fm get top artists by tag failed: {e}")
            return []

    def _fetch_top_albums_by_tag(self, tag: str, limit: int) -> List[Dict[str, Any]]:
        """Blocking: fetch top albums for a tag via pylast."""
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

    async def get_top_albums_by_tag(
        self,
        tag: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get top albums for a tag/genre."""
        if not self.network:
            return []

        try:
            return await asyncio.to_thread(self._fetch_top_albums_by_tag, tag, limit)
        except Exception as e:
            logger.error(f"Last.fm get top albums by tag failed: {e}")
            return []


# Singleton instance
lastfm_service = LastFMService()
