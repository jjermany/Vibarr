"""SABnzbd usenet download client integration."""

from typing import Optional, List, Dict, Any
import logging

import httpx

from app.services import app_settings as cfg

logger = logging.getLogger(__name__)


class NzbInfo:
    """Normalized NZB download information."""

    def __init__(self, data: Dict[str, Any]):
        self.nzo_id = data.get("nzo_id", "")
        self.name = data.get("filename", "") or data.get("name", "")
        self.status = data.get("status", "").lower()
        self.size = _parse_size(data.get("mb", 0))
        self.downloaded = _parse_size(data.get("mbleft", 0))
        self.downloaded = self.size - self.downloaded  # mbleft is remaining
        self.progress = float(data.get("percentage", 0))
        self.eta = data.get("timeleft", "")
        self.category = data.get("cat", "")
        self.storage = data.get("storage", "")  # final path

    @property
    def is_complete(self) -> bool:
        return self.status in ("completed",)

    @property
    def is_downloading(self) -> bool:
        return self.status in ("downloading", "fetching", "grabbing")

    @property
    def is_errored(self) -> bool:
        return self.status in ("failed",)

    @property
    def is_queued(self) -> bool:
        return self.status in ("queued", "paused")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nzo_id": self.nzo_id,
            "name": self.name,
            "status": self.status,
            "progress": round(self.progress, 1),
            "size": self.size,
            "downloaded": self.downloaded,
            "eta": self.eta,
            "category": self.category,
            "storage": self.storage,
            "is_complete": self.is_complete,
            "is_downloading": self.is_downloading,
            "is_errored": self.is_errored,
        }


def _parse_size(val: Any) -> int:
    """Parse SABnzbd size value (in MB) to bytes."""
    try:
        return int(float(val) * 1024 * 1024)
    except (ValueError, TypeError):
        return 0


class SabnzbdService:
    """SABnzbd API client."""

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def is_configured(self) -> bool:
        return bool(cfg.get_optional("sabnzbd_url") and cfg.get_optional("sabnzbd_api_key"))

    def _get_base_url(self) -> str:
        return cfg.get_setting("sabnzbd_url").rstrip("/")

    def _api_params(self, **kwargs: Any) -> Dict[str, Any]:
        """Build common API query params."""
        params = {
            "apikey": cfg.get_setting("sabnzbd_api_key"),
            "output": "json",
        }
        params.update(kwargs)
        return params

    async def _get_client(self) -> Optional[httpx.AsyncClient]:
        if not self.is_configured:
            return None
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._get_base_url(),
                timeout=30.0,
            )
        return self._client

    async def test_connection(self) -> bool:
        """Test connection to SABnzbd."""
        client = await self._get_client()
        if not client:
            return False
        try:
            response = await client.get(
                "/api", params=self._api_params(mode="version")
            )
            if response.status_code == 200:
                data = response.json()
                return "version" in data
            return False
        except Exception as e:
            logger.error(f"SABnzbd connection test failed: {e}")
            return False

    async def get_version(self) -> Optional[str]:
        """Get SABnzbd version."""
        client = await self._get_client()
        if not client:
            return None
        try:
            response = await client.get(
                "/api", params=self._api_params(mode="version")
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("version")
        except Exception as e:
            logger.error(f"Failed to get SABnzbd version: {e}")
        return None

    async def get_categories(self) -> List[str]:
        """Get configured categories from SABnzbd."""
        client = await self._get_client()
        if not client:
            return []
        try:
            response = await client.get(
                "/api", params=self._api_params(mode="get_cats")
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("categories", [])
        except Exception as e:
            logger.error(f"Failed to get SABnzbd categories: {e}")
        return []

    async def add_nzb_url(
        self,
        url: str,
        category: Optional[str] = None,
        name: Optional[str] = None,
    ) -> Optional[str]:
        """Add an NZB by URL. Returns the nzo_id if successful."""
        client = await self._get_client()
        if not client:
            return None
        try:
            params = self._api_params(mode="addurl", name=url)
            sab_cat = category or cfg.get_setting("sabnzbd_category", "music")
            if sab_cat:
                params["cat"] = sab_cat
            if name:
                params["nzbname"] = name

            response = await client.get("/api", params=params)
            if response.status_code == 200:
                data = response.json()
                if data.get("status"):
                    nzo_ids = data.get("nzo_ids", [])
                    return nzo_ids[0] if nzo_ids else None
                else:
                    logger.error(f"SABnzbd add failed: {data.get('error', 'unknown')}")
        except Exception as e:
            logger.error(f"Error adding NZB: {e}")
        return None

    async def get_queue(self) -> List[NzbInfo]:
        """Get the current download queue."""
        client = await self._get_client()
        if not client:
            return []
        try:
            response = await client.get(
                "/api", params=self._api_params(mode="queue")
            )
            if response.status_code == 200:
                data = response.json()
                slots = data.get("queue", {}).get("slots", [])
                return [NzbInfo(s) for s in slots]
        except Exception as e:
            logger.error(f"Failed to get SABnzbd queue: {e}")
        return []

    async def get_history(self, limit: int = 20) -> List[NzbInfo]:
        """Get download history."""
        client = await self._get_client()
        if not client:
            return []
        try:
            response = await client.get(
                "/api", params=self._api_params(mode="history", limit=limit)
            )
            if response.status_code == 200:
                data = response.json()
                slots = data.get("history", {}).get("slots", [])
                return [NzbInfo(s) for s in slots]
        except Exception as e:
            logger.error(f"Failed to get SABnzbd history: {e}")
        return []

    async def get_download(self, nzo_id: str) -> Optional[NzbInfo]:
        """Get a specific download by nzo_id (checks queue then history)."""
        # Check active queue first
        queue = await self.get_queue()
        for item in queue:
            if item.nzo_id == nzo_id:
                return item
        # Check history
        history = await self.get_history(limit=50)
        for item in history:
            if item.nzo_id == nzo_id:
                return item
        return None

    async def pause_download(self, nzo_id: str) -> bool:
        """Pause a download."""
        client = await self._get_client()
        if not client:
            return False
        try:
            response = await client.get(
                "/api", params=self._api_params(mode="queue", name="pause", value=nzo_id)
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to pause NZB: {e}")
            return False

    async def resume_download(self, nzo_id: str) -> bool:
        """Resume a paused download."""
        client = await self._get_client()
        if not client:
            return False
        try:
            response = await client.get(
                "/api", params=self._api_params(mode="queue", name="resume", value=nzo_id)
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to resume NZB: {e}")
            return False

    async def delete_download(self, nzo_id: str, del_files: bool = False) -> bool:
        """Delete a download from the queue."""
        client = await self._get_client()
        if not client:
            return False
        try:
            params = self._api_params(mode="queue", name="delete", value=nzo_id)
            if del_files:
                params["del_files"] = 1
            response = await client.get("/api", params=params)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to delete NZB: {e}")
            return False

    async def delete_history_item(self, nzo_id: str, del_files: bool = False) -> bool:
        """Delete a completed download from history."""
        client = await self._get_client()
        if not client:
            return False
        try:
            params = self._api_params(mode="history", name="delete", value=nzo_id)
            if del_files:
                params["del_files"] = 1
            response = await client.get("/api", params=params)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to delete NZB from history: {e}")
            return False

    async def get_active_count(self) -> int:
        """Get the number of actively downloading NZBs."""
        queue = await self.get_queue()
        return len([q for q in queue if q.is_downloading])


# Singleton instance
sabnzbd_service = SabnzbdService()
