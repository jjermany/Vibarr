"""Deezer API integration for discovery search and artist metadata."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import logging

import httpx

logger = logging.getLogger(__name__)


class DeezerService:
    """Service wrapper around the public Deezer API."""

    BASE_URL = "https://api.deezer.com"
    REQUEST_TIMEOUT = httpx.Timeout(timeout=6.0, connect=2.0)

    @property
    def is_available(self) -> bool:
        """Deezer public API requires no credentials."""
        return True

    async def _get(
        self, path: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Run a Deezer GET request and return JSON data."""
        url = f"{self.BASE_URL}{path}"
        async with httpx.AsyncClient(timeout=self.REQUEST_TIMEOUT) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()

    async def _get_by_url(self, url: str) -> Dict[str, Any]:
        """Run a Deezer GET request against an absolute URL and return JSON data."""
        async with httpx.AsyncClient(timeout=self.REQUEST_TIMEOUT) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()

    def _log_failure(
        self,
        *,
        source: str,
        endpoint_type: str,
        exc: Exception,
        query: str | None = None,
        identifier: int | str | None = None,
    ) -> None:
        """Log actionable Deezer failures with exception details and context."""
        message = (
            "Deezer request failed | source=%s | endpoint=%s | query=%r | "
            "identifier=%r | exc_type=%s | exc=%r"
        )
        args = (source, endpoint_type, query, identifier, type(exc).__name__, exc)

        if isinstance(exc, httpx.TimeoutException):
            logger.warning(message, *args)
            return

        logger.exception(message, *args)

    async def search_artists(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search artists by name."""
        try:
            payload = await self._get("/search/artist", {"q": query, "limit": limit})
            return payload.get("data", []) or []
        except Exception as exc:
            self._log_failure(
                source="deezer artist",
                endpoint_type="search",
                query=query,
                exc=exc,
            )
            return []

    async def search_albums(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search albums by title / text query."""
        try:
            payload = await self._get("/search/album", {"q": query, "limit": limit})
            return payload.get("data", []) or []
        except Exception as exc:
            self._log_failure(
                source="deezer album",
                endpoint_type="search",
                query=query,
                exc=exc,
            )
            return []

    async def search_tracks(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search tracks by title / text query."""
        try:
            payload = await self._get("/search/track", {"q": query, "limit": limit})
            return payload.get("data", []) or []
        except Exception as exc:
            self._log_failure(
                source="deezer track",
                endpoint_type="search",
                query=query,
                exc=exc,
            )
            return []

    async def get_artist(self, artist_id: int | str) -> Optional[Dict[str, Any]]:
        """Get Deezer artist metadata."""
        try:
            return await self._get(f"/artist/{artist_id}")
        except Exception as exc:
            self._log_failure(
                source="deezer artist",
                endpoint_type="get_artist",
                identifier=artist_id,
                exc=exc,
            )
            return None

    async def get_artist_albums(
        self, artist_id: int | str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get artist albums."""
        try:
            payload = await self._get(f"/artist/{artist_id}/albums", {"limit": limit})
            return payload.get("data", []) or []
        except Exception as exc:
            self._log_failure(
                source="deezer album",
                endpoint_type="get_artist_albums",
                identifier=artist_id,
                exc=exc,
            )
            return []

    async def get_artist_top_tracks(
        self, artist_id: int | str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get top tracks for an artist."""
        try:
            payload = await self._get(f"/artist/{artist_id}/top", {"limit": limit})
            return payload.get("data", []) or []
        except Exception as exc:
            self._log_failure(
                source="deezer track",
                endpoint_type="get_artist_top_tracks",
                identifier=artist_id,
                exc=exc,
            )
            return []

    async def get_related_artists(
        self, artist_id: int | str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get related artists for an artist."""
        try:
            payload = await self._get(f"/artist/{artist_id}/related", {"limit": limit})
            return payload.get("data", []) or []
        except Exception as exc:
            self._log_failure(
                source="deezer artist",
                endpoint_type="get_related_artists",
                identifier=artist_id,
                exc=exc,
            )
            return []


    async def get_playlist(self, playlist_id: int | str) -> Optional[Dict[str, Any]]:
        """Get Deezer playlist metadata including embedded tracks."""
        try:
            return await self._get(f"/playlist/{playlist_id}")
        except Exception as exc:
            self._log_failure(
                source="deezer track",
                endpoint_type="get_playlist",
                identifier=playlist_id,
                exc=exc,
            )
            return None

    async def get_playlist_tracks(
        self, playlist_id: int | str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Fetch all tracks for a playlist by following pagination."""
        try:
            payload = await self._get(
                f"/playlist/{playlist_id}/tracks", {"limit": limit, "index": 0}
            )
            tracks = payload.get("data", []) or []

            while True:
                next_url = payload.get("next")
                if next_url:
                    payload = await self._get_by_url(next_url)
                else:
                    total = payload.get("total")
                    if not isinstance(total, int) or len(tracks) >= total:
                        break

                    payload = await self._get(
                        f"/playlist/{playlist_id}/tracks",
                        {"limit": limit, "index": len(tracks)},
                    )

                next_tracks = payload.get("data", []) or []
                if not next_tracks:
                    break
                tracks.extend(next_tracks)

            return tracks
        except Exception as exc:
            self._log_failure(
                source="deezer track",
                endpoint_type="get_playlist_tracks",
                identifier=playlist_id,
                exc=exc,
            )
            return []

    async def get_playlist_with_tracks(
        self, playlist_id: int | str, limit: int = 100
    ) -> Optional[Dict[str, Any]]:
        """Get playlist metadata and ensure embedded track list is fully paginated."""
        playlist = await self.get_playlist(playlist_id)
        if not playlist:
            return None

        tracks = await self.get_playlist_tracks(playlist_id, limit=limit)
        tracks_payload = playlist.get("tracks") or {}
        tracks_payload["data"] = tracks
        tracks_payload["total"] = len(tracks)

        tracks_payload.pop("next", None)

        playlist["tracks"] = tracks_payload
        return playlist


deezer_service = DeezerService()
