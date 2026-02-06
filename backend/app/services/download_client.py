"""qBittorrent download client integration."""

from typing import Optional, List, Dict, Any
import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class TorrentInfo:
    """Normalized torrent information."""

    def __init__(self, data: Dict[str, Any]):
        self.hash = data.get("hash", "")
        self.name = data.get("name", "")
        self.state = data.get("state", "unknown")
        self.progress = data.get("progress", 0.0) * 100  # Convert to 0-100
        self.size = data.get("size", 0)
        self.downloaded = data.get("downloaded", 0)
        self.uploaded = data.get("uploaded", 0)
        self.dl_speed = data.get("dlspeed", 0)
        self.up_speed = data.get("upspeed", 0)
        self.eta = data.get("eta", 0)
        self.num_seeds = data.get("num_seeds", 0)
        self.num_leechs = data.get("num_leechs", 0)
        self.save_path = data.get("save_path", "")
        self.content_path = data.get("content_path", "")
        self.category = data.get("category", "")
        self.added_on = data.get("added_on", 0)
        self.completion_on = data.get("completion_on", 0)

    @property
    def is_complete(self) -> bool:
        """Check if torrent download is complete."""
        return self.state in (
            "uploading", "stalledUP", "pausedUP",
            "queuedUP", "forcedUP", "checkingUP",
        ) or self.progress >= 100.0

    @property
    def is_downloading(self) -> bool:
        return self.state in (
            "downloading", "stalledDL", "forcedDL",
            "checkingDL", "metaDL", "allocating",
        )

    @property
    def is_errored(self) -> bool:
        return self.state in ("error", "missingFiles")

    @property
    def is_paused(self) -> bool:
        return self.state in ("pausedDL", "pausedUP")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hash": self.hash,
            "name": self.name,
            "state": self.state,
            "progress": round(self.progress, 1),
            "size": self.size,
            "dl_speed": self.dl_speed,
            "eta": self.eta,
            "num_seeds": self.num_seeds,
            "save_path": self.save_path,
            "content_path": self.content_path,
            "is_complete": self.is_complete,
            "is_downloading": self.is_downloading,
            "is_errored": self.is_errored,
        }


class DownloadClientService:
    """qBittorrent WebUI API client."""

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        self._authenticated = False

    @property
    def is_configured(self) -> bool:
        return settings.qbittorrent_url is not None

    async def _get_client(self) -> Optional[httpx.AsyncClient]:
        """Get authenticated HTTP client."""
        if not self.is_configured:
            return None

        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=settings.qbittorrent_url.rstrip("/"),
                timeout=30.0,
            )

        if not self._authenticated:
            await self._authenticate()

        return self._client if self._authenticated else None

    async def _authenticate(self) -> bool:
        """Authenticate with qBittorrent WebUI."""
        if not self._client:
            return False

        try:
            response = await self._client.post(
                "/api/v2/auth/login",
                data={
                    "username": settings.qbittorrent_username,
                    "password": settings.qbittorrent_password,
                },
            )
            if response.status_code == 200 and response.text == "Ok.":
                self._authenticated = True
                return True
            else:
                logger.error(f"qBittorrent auth failed: {response.text}")
                return False
        except Exception as e:
            logger.error(f"qBittorrent auth error: {e}")
            return False

    async def test_connection(self) -> bool:
        """Test connection to qBittorrent."""
        client = await self._get_client()
        if not client:
            return False

        try:
            response = await client.get("/api/v2/app/version")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"qBittorrent connection test failed: {e}")
            return False

    async def get_version(self) -> Optional[str]:
        """Get qBittorrent version."""
        client = await self._get_client()
        if not client:
            return None

        try:
            response = await client.get("/api/v2/app/version")
            if response.status_code == 200:
                return response.text
        except Exception as e:
            logger.error(f"Failed to get qBittorrent version: {e}")
        return None

    async def add_torrent_url(
        self,
        url: str,
        category: Optional[str] = None,
        save_path: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> bool:
        """Add a torrent by URL (magnet link or .torrent URL)."""
        client = await self._get_client()
        if not client:
            return False

        try:
            data: Dict[str, Any] = {"urls": url}

            if category or settings.qbittorrent_category:
                data["category"] = category or settings.qbittorrent_category
            if save_path or settings.download_path:
                data["savepath"] = save_path or settings.download_path
            if tags:
                data["tags"] = ",".join(tags)

            response = await client.post("/api/v2/torrents/add", data=data)
            if response.status_code == 200 and response.text == "Ok.":
                return True
            else:
                logger.error(f"Failed to add torrent: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error adding torrent: {e}")
            return False

    async def get_torrent(self, torrent_hash: str) -> Optional[TorrentInfo]:
        """Get info for a specific torrent."""
        client = await self._get_client()
        if not client:
            return None

        try:
            response = await client.get(
                "/api/v2/torrents/info",
                params={"hashes": torrent_hash},
            )
            if response.status_code == 200:
                torrents = response.json()
                if torrents:
                    return TorrentInfo(torrents[0])
        except Exception as e:
            logger.error(f"Failed to get torrent {torrent_hash}: {e}")
        return None

    async def get_torrents(
        self,
        category: Optional[str] = None,
        filter_state: Optional[str] = None,
    ) -> List[TorrentInfo]:
        """Get list of torrents, optionally filtered."""
        client = await self._get_client()
        if not client:
            return []

        try:
            params: Dict[str, Any] = {}
            if category:
                params["category"] = category
            elif settings.qbittorrent_category:
                params["category"] = settings.qbittorrent_category
            if filter_state:
                params["filter"] = filter_state

            response = await client.get("/api/v2/torrents/info", params=params)
            if response.status_code == 200:
                return [TorrentInfo(t) for t in response.json()]
        except Exception as e:
            logger.error(f"Failed to list torrents: {e}")
        return []

    async def pause_torrent(self, torrent_hash: str) -> bool:
        """Pause a torrent."""
        client = await self._get_client()
        if not client:
            return False

        try:
            response = await client.post(
                "/api/v2/torrents/pause",
                data={"hashes": torrent_hash},
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to pause torrent: {e}")
            return False

    async def resume_torrent(self, torrent_hash: str) -> bool:
        """Resume a paused torrent."""
        client = await self._get_client()
        if not client:
            return False

        try:
            response = await client.post(
                "/api/v2/torrents/resume",
                data={"hashes": torrent_hash},
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to resume torrent: {e}")
            return False

    async def delete_torrent(
        self, torrent_hash: str, delete_files: bool = False
    ) -> bool:
        """Delete a torrent."""
        client = await self._get_client()
        if not client:
            return False

        try:
            response = await client.post(
                "/api/v2/torrents/delete",
                data={
                    "hashes": torrent_hash,
                    "deleteFiles": str(delete_files).lower(),
                },
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to delete torrent: {e}")
            return False

    async def get_active_count(self) -> int:
        """Get the number of actively downloading torrents in our category."""
        torrents = await self.get_torrents(filter_state="downloading")
        return len(torrents)

    async def ensure_category(self) -> bool:
        """Ensure our download category exists in qBittorrent."""
        client = await self._get_client()
        if not client:
            return False

        try:
            response = await client.post(
                "/api/v2/torrents/createCategory",
                data={
                    "category": settings.qbittorrent_category,
                    "savePath": settings.download_path,
                },
            )
            # 409 means category already exists, which is fine
            return response.status_code in (200, 409)
        except Exception as e:
            logger.error(f"Failed to create category: {e}")
            return False


# Singleton instance
download_client_service = DownloadClientService()
