"""Spotify API integration for metadata and recommendations."""

from typing import Optional, List, Dict, Any
import asyncio
import logging

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

from app.services import app_settings as cfg

logger = logging.getLogger(__name__)


class SpotifyService:
    """Spotify API service for metadata and recommendations."""

    def __init__(self):
        """Initialize Spotify client."""
        self._client: Optional[spotipy.Spotify] = None

    @property
    def client(self) -> Optional[spotipy.Spotify]:
        """Get or create Spotify client."""
        client_id = cfg.get_optional("spotify_client_id")
        client_secret = cfg.get_optional("spotify_client_secret")
        if self._client is None and client_id and client_secret:
            try:
                auth_manager = SpotifyClientCredentials(
                    client_id=client_id,
                    client_secret=client_secret,
                )
                self._client = spotipy.Spotify(auth_manager=auth_manager)
            except Exception as e:
                logger.error(f"Failed to initialize Spotify client: {e}")
        return self._client

    @property
    def is_available(self) -> bool:
        """Check if Spotify service is available."""
        return self.client is not None

    async def search_artists(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search for artists."""
        if not self.client:
            return []

        try:
            results = await asyncio.to_thread(
                self.client.search, q=query, type="artist", limit=limit
            )
            return results.get("artists", {}).get("items", [])
        except Exception as e:
            logger.error(f"Spotify artist search failed: {e}")
            return []

    async def search_albums(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search for albums."""
        if not self.client:
            return []

        try:
            results = await asyncio.to_thread(
                self.client.search, q=query, type="album", limit=limit
            )
            return results.get("albums", {}).get("items", [])
        except Exception as e:
            logger.error(f"Spotify album search failed: {e}")
            return []

    async def search_tracks(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search for tracks."""
        if not self.client:
            return []

        try:
            results = await asyncio.to_thread(
                self.client.search, q=query, type="track", limit=limit
            )
            return results.get("tracks", {}).get("items", [])
        except Exception as e:
            logger.error(f"Spotify track search failed: {e}")
            return []

    async def get_artist(self, spotify_id: str) -> Optional[Dict[str, Any]]:
        """Get artist by Spotify ID."""
        if not self.client:
            return None

        try:
            return await asyncio.to_thread(self.client.artist, spotify_id)
        except Exception as e:
            logger.error(f"Spotify get artist failed: {e}")
            return None

    async def get_artist_albums(
        self,
        spotify_id: str,
        album_type: str = "album,single,ep",
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get artist's albums."""
        if not self.client:
            return []

        try:
            results = await asyncio.to_thread(
                self.client.artist_albums,
                spotify_id,
                album_type=album_type,
                limit=limit,
            )
            return results.get("items", [])
        except Exception as e:
            logger.error(f"Spotify get artist albums failed: {e}")
            return []

    async def get_related_artists(self, spotify_id: str) -> List[Dict[str, Any]]:
        """Get related artists (Spotify's recommendation)."""
        if not self.client:
            return []

        try:
            results = await asyncio.to_thread(
                self.client.artist_related_artists, spotify_id
            )
            return results.get("artists", [])
        except Exception as e:
            logger.error(f"Spotify get related artists failed: {e}")
            return []

    async def get_album(self, spotify_id: str) -> Optional[Dict[str, Any]]:
        """Get album by Spotify ID."""
        if not self.client:
            return None

        try:
            return await asyncio.to_thread(self.client.album, spotify_id)
        except Exception as e:
            logger.error(f"Spotify get album failed: {e}")
            return None

    async def get_album_tracks(self, spotify_id: str) -> List[Dict[str, Any]]:
        """Get album tracks."""
        if not self.client:
            return []

        try:
            results = await asyncio.to_thread(
                self.client.album_tracks, spotify_id, limit=50
            )
            return results.get("items", [])
        except Exception as e:
            logger.error(f"Spotify get album tracks failed: {e}")
            return []

    async def get_audio_features(self, track_ids: List[str]) -> List[Dict[str, Any]]:
        """Get audio features for multiple tracks."""
        if not self.client or not track_ids:
            return []

        try:
            # Spotify allows max 100 tracks per request
            all_features = []
            for i in range(0, len(track_ids), 100):
                batch = track_ids[i:i + 100]
                features = await asyncio.to_thread(self.client.audio_features, batch)
                all_features.extend([f for f in features if f])
            return all_features
        except Exception as e:
            logger.error(f"Spotify get audio features failed: {e}")
            return []

    async def get_recommendations(
        self,
        seed_artists: List[str] = None,
        seed_tracks: List[str] = None,
        seed_genres: List[str] = None,
        limit: int = 20,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """
        Get recommendations based on seeds.

        Additional kwargs can include audio feature targets:
        - target_danceability, target_energy, target_valence, etc.
        - min_*, max_* variants for ranges
        """
        if not self.client:
            return []

        try:
            results = await asyncio.to_thread(
                self.client.recommendations,
                seed_artists=seed_artists or [],
                seed_tracks=seed_tracks or [],
                seed_genres=seed_genres or [],
                limit=limit,
                **kwargs,
            )
            return results.get("tracks", [])
        except Exception as e:
            logger.error(f"Spotify get recommendations failed: {e}")
            return []

    async def get_available_genre_seeds(self) -> List[str]:
        """Get available genre seeds for recommendations."""
        if not self.client:
            return []

        try:
            results = await asyncio.to_thread(self.client.recommendation_genre_seeds)
            return results.get("genres", [])
        except Exception as e:
            logger.error(f"Spotify get genre seeds failed: {e}")
            return []

    async def get_new_releases(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get new album releases."""
        if not self.client:
            return []

        try:
            results = await asyncio.to_thread(self.client.new_releases, limit=limit)
            return results.get("albums", {}).get("items", [])
        except Exception as e:
            logger.error(f"Spotify get new releases failed: {e}")
            return []


# Singleton instance
spotify_service = SpotifyService()
