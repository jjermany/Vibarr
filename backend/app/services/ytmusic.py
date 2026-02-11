"""YouTube Music integration for fallback artist and metadata lookups."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import logging

from ytmusicapi import YTMusic

logger = logging.getLogger(__name__)


class YTMusicService:
    """Wrapper around ytmusicapi for fallback catalog depth."""

    def __init__(self):
        self._client: Optional[YTMusic] = None

    @property
    def client(self) -> Optional[YTMusic]:
        if self._client is None:
            try:
                self._client = YTMusic()
            except Exception as exc:
                logger.error(f"Failed to initialize YTMusic client: {exc}")
                self._client = None
        return self._client

    @property
    def is_available(self) -> bool:
        return self.client is not None

    async def search(
        self, query: str, filter: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        if not self.client:
            return []
        try:
            return self.client.search(query=query, filter=filter, limit=limit) or []
        except Exception as exc:
            logger.error(f"YTMusic search failed ({filter}): {exc}")
            return []

    async def search_artists(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        return await self.search(query=query, filter="artists", limit=limit)

    async def search_albums(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        return await self.search(query=query, filter="albums", limit=limit)

    async def search_tracks(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        songs = await self.search(query=query, filter="songs", limit=limit)
        if songs:
            return songs
        return await self.search(query=query, filter="videos", limit=limit)

    async def get_artist(self, browse_id: str) -> Optional[Dict[str, Any]]:
        if not self.client:
            return None
        try:
            return self.client.get_artist(channelId=browse_id)
        except Exception as exc:
            logger.error(f"YTMusic get_artist failed: {exc}")
            return None


ytmusic_service = YTMusicService()
