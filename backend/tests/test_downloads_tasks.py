import pytest

from app.models.download import DownloadStatus
from app.models.wishlist import WishlistItem, WishlistStatus
from app.tasks import downloads


async def _noop_async():
    return None


class _ScalarResult:
    def __init__(self, item):
        self._item = item

    def scalar_one_or_none(self):
        return self._item


class _FakeSession:
    def __init__(self, item):
        self.item = item
        self.added = []

    async def execute(self, _query):
        return _ScalarResult(self.item)

    def add(self, model):
        self.added.append(model)

    async def commit(self):
        return None

    async def refresh(self, model):
        if getattr(model, "id", None) is None:
            model.id = 999


class _SessionFactory:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeProwlarrService:
    def __init__(self, results):
        self.is_available = True
        self._results = results

    async def search_album(self, **_kwargs):
        return self._results


class _FakeDownloadClientService:
    def __init__(self, active_count=0, is_configured=True):
        self.is_configured = is_configured
        self._active_count = active_count

    async def get_active_count(self):
        return self._active_count


@pytest.mark.asyncio
async def test_search_wishlist_item_found_creates_download_row(monkeypatch):
    item = WishlistItem(
        id=1,
        item_type="album",
        artist_name="Artist",
        album_title="Album",
        status=WishlistStatus.WANTED,
        search_count=0,
    )
    session = _FakeSession(item)

    monkeypatch.setattr(downloads.cfg, "ensure_cache", _noop_async)
    monkeypatch.setattr(
        downloads,
        "prowlarr_service",
        _FakeProwlarrService(
            [
                {
                    "indexer": "TestIndexer",
                    "indexer_id": 42,
                    "title": "Artist - Album FLAC",
                    "size": 1234,
                    "format": "flac",
                    "quality": "lossless",
                    "seeders": 5,
                    "leechers": 1,
                    "score": 10,
                    "guid": "abc",
                }
            ]
        ),
    )
    monkeypatch.setattr(downloads, "AsyncSessionLocal", lambda: _SessionFactory(session))
    monkeypatch.setattr(downloads.cfg, "get_bool", lambda *args, **kwargs: False)

    payload = await downloads._search_wishlist_item_async(item_id=1)

    assert payload["status"] == "found"
    assert payload["results_count"] == 1
    assert payload["download_id"] == 999
    assert item.status == WishlistStatus.FOUND
    assert len(session.added) == 1

    created = session.added[0]
    assert created.wishlist_id == 1
    assert created.artist_name == "Artist"
    assert created.album_title == "Album"
    assert created.search_query == "Artist Album"
    assert created.status == DownloadStatus.FOUND
    assert created.source == "wishlist"
    assert created.indexer_name == "TestIndexer"
    assert created.indexer_id == "42"


@pytest.mark.asyncio
async def test_search_wishlist_item_without_results_returns_wanted(monkeypatch):
    item = WishlistItem(
        id=2,
        item_type="album",
        artist_name="Artist",
        album_title="Missing",
        status=WishlistStatus.WANTED,
        search_count=0,
    )
    session = _FakeSession(item)

    monkeypatch.setattr(downloads.cfg, "ensure_cache", _noop_async)
    monkeypatch.setattr(downloads, "prowlarr_service", _FakeProwlarrService([]))
    monkeypatch.setattr(downloads, "AsyncSessionLocal", lambda: _SessionFactory(session))

    payload = await downloads._search_wishlist_item_async(item_id=2)

    assert payload == {"status": "not_found"}
    assert item.status == WishlistStatus.WANTED
    assert session.added == []


@pytest.mark.asyncio
async def test_search_wishlist_item_auto_grab_enqueues_task_when_threshold_met(monkeypatch):
    item = WishlistItem(
        id=3,
        item_type="album",
        artist_name="Artist",
        album_title="Album",
        status=WishlistStatus.WANTED,
        search_count=0,
        auto_download=True,
    )
    session = _FakeSession(item)
    grabbed = {}

    monkeypatch.setattr(downloads.cfg, "ensure_cache", _noop_async)
    monkeypatch.setattr(
        downloads,
        "prowlarr_service",
        _FakeProwlarrService(
            [
                {
                    "indexer": "TestIndexer",
                    "indexer_id": 7,
                    "title": "Artist - Album FLAC",
                    "score": 85,
                    "guid": "release-guid",
                }
            ]
        ),
    )
    monkeypatch.setattr(downloads, "AsyncSessionLocal", lambda: _SessionFactory(session))
    monkeypatch.setattr(
        downloads,
        "download_client_service",
        _FakeDownloadClientService(active_count=0, is_configured=True),
    )

    def fake_delay(**kwargs):
        grabbed.update(kwargs)

    def fake_get_bool(key, default=False):
        return True if key == "auto_download_enabled" else default

    def fake_get_float(key, default=0.0):
        return 0.8 if key == "auto_download_confidence_threshold" else default

    def fake_get_int(key, default=0):
        return 3 if key == "max_concurrent_downloads" else default

    monkeypatch.setattr(downloads.cfg, "get_bool", fake_get_bool)
    monkeypatch.setattr(downloads.cfg, "get_float", fake_get_float)
    monkeypatch.setattr(downloads.cfg, "get_int", fake_get_int)
    monkeypatch.setattr(downloads.grab_release, "delay", fake_delay)

    payload = await downloads._search_wishlist_item_async(item_id=3)

    assert payload["status"] == "found"
    assert payload["download_id"] == 999
    assert grabbed == {
        "download_id": 999,
        "guid": "release-guid",
        "indexer_id": 7,
    }
