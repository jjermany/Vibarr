"""Prowlarr API integration for indexer search and download management."""

from typing import Optional, List, Dict, Any
import logging
import asyncio

import httpx

from app.services import app_settings as cfg

logger = logging.getLogger(__name__)


class ProwlarrService:
    """Prowlarr API service for searching indexers and managing downloads."""

    def __init__(self):
        """Initialize Prowlarr client."""
        self._client: Optional[httpx.AsyncClient] = None
        self._client_loop: Optional[asyncio.AbstractEventLoop] = None

    @property
    def client(self) -> Optional[httpx.AsyncClient]:
        """Get HTTP client."""
        url = cfg.get_optional("prowlarr_url")
        api_key = cfg.get_optional("prowlarr_api_key")

        current_loop = None
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            pass

        if self._client is not None and (
            self._client.is_closed
            or (
                current_loop is not None
                and self._client_loop is not None
                and self._client_loop is not current_loop
            )
        ):
            self._client = None
            self._client_loop = None

        if self._client is None and url and api_key:
            self._client = httpx.AsyncClient(
                base_url=url.rstrip("/"),
                headers={"X-Api-Key": api_key},
                timeout=30.0,
            )
            self._client_loop = current_loop

        return self._client

    async def close(self) -> None:
        """Close any cached async HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

        self._client = None
        self._client_loop = None

    @property
    def is_available(self) -> bool:
        """Check if Prowlarr service is available."""
        return bool(cfg.get_optional("prowlarr_url") and cfg.get_optional("prowlarr_api_key"))

    async def test_connection(self) -> bool:
        """Test connection to Prowlarr."""
        if not self.client:
            return False

        try:
            response = await self.client.get("/api/v1/health")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Prowlarr connection test failed: {e}")
            return False

    async def get_indexers(self) -> List[Dict[str, Any]]:
        """Get all configured indexers."""
        if not self.client:
            return []

        try:
            response = await self.client.get("/api/v1/indexer")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Prowlarr get indexers failed: {e}")
            return []

    async def search(
        self,
        query: str,
        categories: List[int] = None,
        indexer_ids: List[int] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Search across all indexers.

        Categories for music:
        - 3000: Audio
        - 3010: Audio/MP3
        - 3020: Audio/Video
        - 3030: Audio/Audiobook
        - 3040: Audio/Lossless
        """
        if not self.client:
            return []

        # Default to audio categories if not specified
        if categories is None:
            categories = [3000, 3010, 3040]  # Audio, MP3, Lossless

        try:
            params = {
                "query": query,
                "categories": categories,
                "limit": limit,
                "type": "search",
            }

            if indexer_ids:
                params["indexerIds"] = indexer_ids

            response = await self.client.get("/api/v1/search", params=params)
            response.raise_for_status()

            results = response.json()

            # Parse and normalize results
            normalized = []
            for result in results:
                normalized.append({
                    "guid": result.get("guid"),
                    "indexer": result.get("indexer"),
                    "indexer_id": result.get("indexerId"),
                    "title": result.get("title"),
                    "size": result.get("size"),
                    "seeders": result.get("seeders"),
                    "leechers": result.get("leechers"),
                    "protocol": result.get("protocol"),
                    "download_url": result.get("downloadUrl"),
                    "info_url": result.get("infoUrl"),
                    "publish_date": result.get("publishDate"),
                    "categories": result.get("categories", []),
                    # Parsed info
                    "quality": self._parse_quality(result.get("title", "")),
                    "format": self._parse_format(result.get("title", "")),
                })

            return normalized
        except Exception as e:
            logger.error(f"Prowlarr search failed: {e}")
            return []

    async def search_album(
        self,
        artist: str,
        album: str,
        year: int = None,
        preferred_format: str = None,
    ) -> List[Dict[str, Any]]:
        """Search for a specific album."""
        # Build search query
        query = f"{artist} {album}"
        if year:
            query += f" {year}"

        results = await self.search(query)

        # Score and sort results
        scored_results = []
        for result in results:
            score = self._score_result(
                result,
                artist=artist,
                album=album,
                preferred_format=preferred_format,
            )
            result["score"] = score
            scored_results.append(result)

        # Sort by score descending
        scored_results.sort(key=lambda x: x["score"], reverse=True)

        return scored_results

    async def grab(
        self,
        guid: str,
        indexer_id: int,
    ) -> Optional[str]:
        """
        Grab a release and send to download client.

        Returns the download ID if successful.
        """
        if not self.client:
            return None

        try:
            response = await self.client.post(
                "/api/v1/search",
                json={
                    "guid": guid,
                    "indexerId": indexer_id,
                },
            )
            response.raise_for_status()
            return response.json().get("id")
        except Exception as e:
            logger.error(f"Prowlarr grab failed: {e}")
            return None

    async def get_download_clients(self) -> List[Dict[str, Any]]:
        """Get configured download clients."""
        if not self.client:
            return []

        try:
            response = await self.client.get("/api/v1/downloadclient")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Prowlarr get download clients failed: {e}")
            return []

    def _parse_quality(self, title: str) -> Optional[str]:
        """Parse quality from release title."""
        title_lower = title.lower()

        if "flac" in title_lower or "lossless" in title_lower:
            if "24bit" in title_lower or "24-bit" in title_lower or "hi-res" in title_lower:
                return "flac-24"
            return "flac"
        elif "320" in title_lower:
            return "320"
        elif "v0" in title_lower:
            return "v0"
        elif "256" in title_lower:
            return "256"
        elif "192" in title_lower:
            return "192"
        elif "mp3" in title_lower:
            return "mp3"

        return None

    def _parse_format(self, title: str) -> Optional[str]:
        """Parse format from release title."""
        title_lower = title.lower()

        if "flac" in title_lower:
            return "flac"
        elif "mp3" in title_lower:
            return "mp3"
        elif "aac" in title_lower:
            return "aac"
        elif "ogg" in title_lower:
            return "ogg"
        elif "opus" in title_lower:
            return "opus"

        return None

    def _score_result(
        self,
        result: Dict[str, Any],
        artist: str,
        album: str,
        preferred_format: str = None,
    ) -> float:
        """
        Score a search result for quality matching.

        Higher score = better match.
        """
        score = 0.0
        title = result.get("title", "").lower()
        artist_lower = artist.lower()
        album_lower = album.lower()

        # Title matching (max 50 points)
        if artist_lower in title:
            score += 25
        if album_lower in title:
            score += 25

        # Format preference (max 30 points)
        quality = result.get("quality")
        if preferred_format:
            if preferred_format == "flac" and quality in ["flac", "flac-24"]:
                score += 30
            elif preferred_format == "320" and quality == "320":
                score += 30
            elif preferred_format == "v0" and quality == "v0":
                score += 30
        else:
            # Default preference: FLAC > 320 > V0 > other
            if quality == "flac-24":
                score += 30
            elif quality == "flac":
                score += 28
            elif quality == "320":
                score += 25
            elif quality == "v0":
                score += 22

        # Seeders (max 15 points)
        seeders = result.get("seeders", 0)
        if seeders > 100:
            score += 15
        elif seeders > 50:
            score += 12
        elif seeders > 20:
            score += 9
        elif seeders > 5:
            score += 6
        elif seeders > 0:
            score += 3

        # Size sanity check (max 5 points)
        size = result.get("size", 0)
        size_mb = size / (1024 * 1024)
        if 50 < size_mb < 2000:  # Reasonable album size
            score += 5

        return score


# Singleton instance
prowlarr_service = ProwlarrService()
