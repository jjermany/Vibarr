"""Deezer API integration for discovery search and artist metadata."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import logging

import httpx

logger = logging.getLogger(__name__)


class DeezerService:
    """Service wrapper around the public Deezer API."""

    BASE_URL = "https://api.deezer.com"

    @property
    def is_available(self) -> bool:
        """Deezer public API requires no credentials."""
        return True

    async def _get(
        self, path: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Run a Deezer GET request and return JSON data."""
        url = f"{self.BASE_URL}{path}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()

    async def search_artists(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search artists by name."""
        try:
            payload = await self._get("/search/artist", {"q": query, "limit": limit})
            return payload.get("data", []) or []
        except Exception as exc:
            logger.error(f"Deezer artist search failed: {exc}")
            return []

    async def search_albums(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search albums by title / text query."""
        try:
            payload = await self._get("/search/album", {"q": query, "limit": limit})
            return payload.get("data", []) or []
        except Exception as exc:
            logger.error(f"Deezer album search failed: {exc}")
            return []

    async def search_tracks(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search tracks by title / text query."""
        try:
            payload = await self._get("/search/track", {"q": query, "limit": limit})
            return payload.get("data", []) or []
        except Exception as exc:
            logger.error(f"Deezer track search failed: {exc}")
            return []

    async def get_artist(self, artist_id: int | str) -> Optional[Dict[str, Any]]:
        """Get Deezer artist metadata."""
        try:
            return await self._get(f"/artist/{artist_id}")
        except Exception as exc:
            logger.error(f"Deezer get artist failed: {exc}")
            return None

    async def get_artist_albums(
        self, artist_id: int | str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get artist albums."""
        try:
            payload = await self._get(f"/artist/{artist_id}/albums", {"limit": limit})
            return payload.get("data", []) or []
        except Exception as exc:
            logger.error(f"Deezer get artist albums failed: {exc}")
            return []

    async def get_artist_top_tracks(
        self, artist_id: int | str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get top tracks for an artist."""
        try:
            payload = await self._get(f"/artist/{artist_id}/top", {"limit": limit})
            return payload.get("data", []) or []
        except Exception as exc:
            logger.error(f"Deezer get artist top tracks failed: {exc}")
            return []

    async def get_related_artists(
        self, artist_id: int | str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get related artists for an artist."""
        try:
            payload = await self._get(f"/artist/{artist_id}/related", {"limit": limit})
            return payload.get("data", []) or []
        except Exception as exc:
            logger.error(f"Deezer related artists failed: {exc}")
            return []


    async def get_playlist(self, playlist_id: int | str) -> Optional[Dict[str, Any]]:
        """Get Deezer playlist metadata including embedded tracks."""
        try:
            return await self._get(f"/playlist/{playlist_id}")
        except Exception as exc:
            logger.error(f"Deezer get playlist failed: {exc}")
            return None


deezer_service = DeezerService()
