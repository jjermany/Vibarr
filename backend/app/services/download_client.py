"""qBittorrent download client integration."""

from typing import Optional, List, Dict, Any
import logging
import re
import asyncio

import httpx

from app.services import app_settings as cfg

logger = logging.getLogger(__name__)

_NON_WORD_RE = re.compile(r"[^a-z0-9]+")


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
        return bool(cfg.get_optional("qbittorrent_url"))

    async def _get_client(self) -> Optional[httpx.AsyncClient]:
        """Get authenticated HTTP client."""
        if not self.is_configured:
            return None

        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=cfg.get_setting("qbittorrent_url").rstrip("/"),
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
                    "username": cfg.get_setting("qbittorrent_username", "admin"),
                    "password": cfg.get_setting("qbittorrent_password"),
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
        """Add a torrent by URL (magnet link or .torrent URL).

        If ``qbittorrent_incomplete_path`` is configured the torrent is
        saved there initially; qBittorrent will move it to the category's
        save-path (or ``download_path``) once complete.
        """
        client = await self._get_client()
        if not client:
            return False

        try:
            data: Dict[str, Any] = {"urls": url}

            qbit_cat = cfg.get_setting("qbittorrent_category", "vibarr")
            if category or qbit_cat:
                data["category"] = category or qbit_cat

            # Use incomplete path for active downloads when configured;
            # qBittorrent moves finished torrents to the category save-path.
            incomplete = cfg.get_setting("qbittorrent_incomplete_path")
            dl_path = cfg.get_setting("download_path", "/downloads")
            if save_path:
                data["savepath"] = save_path
            elif incomplete:
                data["savepath"] = incomplete
            elif dl_path:
                data["savepath"] = dl_path

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

    @staticmethod
    def _normalize_title(value: str) -> str:
        """Normalize title for fuzzy comparisons."""
        return _NON_WORD_RE.sub("", (value or "").lower())

    async def find_torrent_hash(
        self,
        release_title: str,
        timeout_seconds: int = 15,
        poll_interval_seconds: float = 1.0,
    ) -> Optional[str]:
        """Poll qBittorrent and return the hash of the added torrent when found."""
        normalized_target = self._normalize_title(release_title)
        if not normalized_target:
            return None

        elapsed = 0.0
        while elapsed <= timeout_seconds:
            torrents = await self.get_torrents()
            for torrent in torrents:
                normalized_name = self._normalize_title(torrent.name)
                if normalized_name == normalized_target or normalized_target in normalized_name:
                    return torrent.hash

            await asyncio.sleep(poll_interval_seconds)
            elapsed += poll_interval_seconds

        return None

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
            elif cfg.get_setting("qbittorrent_category", "vibarr"):
                params["category"] = cfg.get_setting("qbittorrent_category", "vibarr")
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
        """Ensure our default download category exists in qBittorrent."""
        cat = cfg.get_setting("qbittorrent_category", "vibarr")
        save_path = cfg.get_setting("download_path", "/downloads")
        return await self.ensure_category_by_name(cat, save_path)

    async def ensure_category_by_name(
        self, category: str, save_path: str = ""
    ) -> bool:
        """Create a category in qBittorrent if it doesn't already exist."""
        client = await self._get_client()
        if not client:
            return False

        try:
            data: Dict[str, Any] = {"category": category}
            if save_path:
                data["savePath"] = save_path
            response = await client.post(
                "/api/v2/torrents/createCategory", data=data
            )
            # 409 means category already exists, which is fine
            return response.status_code in (200, 409)
        except Exception as e:
            logger.error(f"Failed to create category '{category}': {e}")
            return False

    async def ensure_all_categories(self) -> List[str]:
        """Ensure all user-configured categories exist in qBittorrent."""
        raw = cfg.get_setting("qbittorrent_categories", "vibarr,music")
        categories = [c.strip() for c in raw.split(",") if c.strip()]
        save_path = cfg.get_setting("download_path", "/downloads")

        created = []
        for cat in categories:
            if await self.ensure_category_by_name(cat, save_path):
                created.append(cat)
        return created

    async def get_categories(self) -> Dict[str, Any]:
        """Get all categories from qBittorrent."""
        client = await self._get_client()
        if not client:
            return {}

        try:
            response = await client.get("/api/v2/torrents/categories")
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"Failed to get categories: {e}")
        return {}

    async def set_torrent_category(
        self, torrent_hash: str, category: str
    ) -> bool:
        """Set category on an existing torrent."""
        client = await self._get_client()
        if not client:
            return False

        try:
            response = await client.post(
                "/api/v2/torrents/setCategory",
                data={"hashes": torrent_hash, "category": category},
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to set category: {e}")
            return False


# Singleton instance
download_client_service = DownloadClientService()
