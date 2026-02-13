import asyncio
import time

import pytest

from app.services.ytmusic import YTMusicService


@pytest.mark.asyncio
async def test_search_runs_in_thread_and_can_timeout():
    service = YTMusicService()

    class SlowClient:
        def search(self, query, filter=None, scope=None, limit=20):
            time.sleep(0.25)
            return [{"artist": "x"}]

    service._client = SlowClient()

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(service.search_artists("query", limit=5), timeout=0.05)


@pytest.mark.asyncio
async def test_get_playlist_uses_threaded_call():
    service = YTMusicService()

    class Client:
        def get_playlist(self, playlistId, limit=None):
            return {"id": playlistId, "limit": limit}

    service._client = Client()

    result = await service.get_playlist("PL123", limit=10)

    assert result == {"id": "PL123", "limit": 10}
