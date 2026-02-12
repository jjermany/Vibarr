import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.models.download import Download, DownloadStatus
from app.models.wishlist import WishlistItem, WishlistStatus
from app.routers import wishlist as wishlist_router
from app.tasks import downloads


async def _noop_async():
    return None


class _ScalarResult:
    def __init__(self, item):
        self._item = item

    def scalar_one_or_none(self):
        return self._item


class _FakeRouterDb:
    def __init__(self, item):
        self.item = item

    async def execute(self, _query):
        return _ScalarResult(self.item)


class _SessionFactory:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeTaskSession:
    def __init__(self, *, download=None, wishlist=None):
        self.download = download
        self.wishlist = wishlist
        self.added = []

    async def execute(self, query):
        entity = query.column_descriptions[0].get("entity")
        if entity is WishlistItem:
            return _ScalarResult(self.wishlist)
        if entity is Download:
            return _ScalarResult(self.download)
        return _ScalarResult(None)

    def add(self, model):
        self.added.append(model)

    async def commit(self):
        return None

    async def refresh(self, model):
        if getattr(model, "id", None) is None:
            model.id = 101


class _FakeProwlarrSearch:
    is_available = True

    def __init__(self, results):
        self.results = results

    async def search_album(self, **_kwargs):
        return self.results


class _FakeProwlarrGrab:
    is_available = True

    def __init__(self, grab_result):
        self.grab_result = grab_result

    async def grab(self, *_args, **_kwargs):
        return self.grab_result


class _FakeImportResult:
    def __init__(self, success, error=None):
        self.success = success
        self.error = error
        self.albums_imported = 1
        self.tracks_imported = 10
        self.final_path = "/library/artist/album"


class _FakeBeetsService:
    is_available = True

    def __init__(self, result):
        self.result = result

    async def import_directory(self, **_kwargs):
        return self.result


class _FakeDownloadClient:
    is_configured = True

    async def get_torrent(self, _download_id):
        return None


@pytest.mark.asyncio
async def test_post_search_wishlist_queues_task_and_returns_immediate_response(monkeypatch):
    item = WishlistItem(id=44, item_type="album", status=WishlistStatus.WANTED)
    fake_db = _FakeRouterDb(item)
    queued = {}

    async def override_get_db():
        yield fake_db

    def fake_delay(item_id):
        queued["item_id"] = item_id

    monkeypatch.setattr(wishlist_router, "prowlarr_service", type("_Svc", (), {"is_available": True})())
    monkeypatch.setattr(downloads.search_wishlist_item, "delay", fake_delay)

    app = FastAPI()
    app.include_router(wishlist_router.router, prefix="/api/wishlist")
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post("/api/wishlist/44/search")

    assert response.status_code == 200
    assert response.json() == {"status": "search_queued", "id": 44}
    assert queued == {"item_id": 44}


@pytest.mark.asyncio
async def test_search_wishlist_item_async_creates_download_metadata_from_prowlarr(monkeypatch):
    item = WishlistItem(
        id=1,
        item_type="album",
        artist_name="Massive Attack",
        album_title="Mezzanine",
        status=WishlistStatus.WANTED,
        search_count=0,
    )
    session = _FakeTaskSession(wishlist=item)

    monkeypatch.setattr(downloads.cfg, "ensure_cache", _noop_async)
    monkeypatch.setattr(
        downloads,
        "prowlarr_service",
        _FakeProwlarrSearch(
            [
                {
                    "indexer": "IndexerA",
                    "indexer_id": 77,
                    "title": "Massive Attack - Mezzanine FLAC",
                    "size": 5555,
                    "format": "flac",
                    "quality": "lossless",
                    "seeders": 99,
                    "leechers": 2,
                    "score": 97,
                    "guid": "guid-1",
                }
            ]
        ),
    )
    monkeypatch.setattr(downloads, "AsyncSessionLocal", lambda: _SessionFactory(session))
    monkeypatch.setattr(downloads.cfg, "get_bool", lambda *args, **kwargs: False)

    payload = await downloads._search_wishlist_item_async(item_id=1)

    assert payload == {"status": "found", "results_count": 1, "download_id": 101}
    assert item.status == WishlistStatus.FOUND
    assert len(session.added) == 1
    created = session.added[0]
    assert created.search_query == "Massive Attack Mezzanine"
    assert created.indexer_name == "IndexerA"
    assert created.indexer_id == "77"
    assert created.release_title == "Massive Attack - Mezzanine FLAC"
    assert created.release_format == "flac"
    assert created.release_quality == "lossless"
    assert created.seeders == 99
    assert created.leechers == 2
    assert created.status == DownloadStatus.FOUND


@pytest.mark.asyncio
async def test_grab_and_import_status_propagation_updates_download_and_wishlist(monkeypatch):
    wishlist = WishlistItem(id=20, item_type="album", status=WishlistStatus.FOUND)
    download = Download(
        id=200,
        wishlist_id=20,
        artist_name="Artist",
        album_title="Album",
        status=DownloadStatus.FOUND,
    )
    session = _FakeTaskSession(download=download, wishlist=wishlist)

    monkeypatch.setattr(downloads.cfg, "ensure_cache", _noop_async)
    monkeypatch.setattr(downloads, "AsyncSessionLocal", lambda: _SessionFactory(session))
    monkeypatch.setattr(downloads, "prowlarr_service", _FakeProwlarrGrab("client-id"))

    grabbed = await downloads._grab_release_async(download_id=200, guid="g", indexer_id=1)

    assert grabbed["status"] == "grabbed"
    assert download.status == DownloadStatus.DOWNLOADING
    assert wishlist.status == WishlistStatus.DOWNLOADING

    download.download_path = "/downloads/album"
    monkeypatch.setattr(
        downloads,
        "beets_service",
        _FakeBeetsService(_FakeImportResult(success=True)),
    )

    imported = await downloads._import_completed_download_async(download_id=200)

    assert imported["status"] == "completed"
    assert download.status == DownloadStatus.COMPLETED
    assert wishlist.status == WishlistStatus.DOWNLOADED


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scenario,setup,assertions",
    [
        (
            "grab_failure",
            lambda monkeypatch: monkeypatch.setattr(
                downloads, "prowlarr_service", _FakeProwlarrGrab(None)
            ),
            lambda result, download, wishlist: (
                result["status"] == "error"
                and download.status == DownloadStatus.FAILED
                and wishlist.status == WishlistStatus.FAILED
                and "Failed to grab" in (wishlist.notes or "")
            ),
        ),
        (
            "missing_torrent_or_path",
            lambda monkeypatch: monkeypatch.setattr(
                downloads, "download_client_service", _FakeDownloadClient()
            ),
            lambda result, download, wishlist: (
                result["status"] == "error"
                and download.status == DownloadStatus.FAILED
                and wishlist.status == WishlistStatus.FAILED
                and "No download path" in (result["message"])
            ),
        ),
        (
            "import_failure",
            lambda monkeypatch: monkeypatch.setattr(
                downloads,
                "beets_service",
                _FakeBeetsService(_FakeImportResult(success=False, error="bad tags")),
            ),
            lambda result, download, wishlist: (
                result["status"] == "completed"
                and download.status == DownloadStatus.FAILED
                and wishlist.status == WishlistStatus.FAILED
                and "Beets import failed" in (wishlist.notes or "")
            ),
        ),
    ],
)
async def test_failure_paths_are_user_visible_and_recoverable(
    monkeypatch, scenario, setup, assertions
):
    wishlist = WishlistItem(id=30, item_type="album", status=WishlistStatus.FOUND)
    download = Download(
        id=300,
        wishlist_id=30,
        artist_name="Artist",
        album_title="Album",
        status=DownloadStatus.FOUND,
        download_id="hash",
    )

    if scenario == "missing_torrent_or_path":
        download.status = DownloadStatus.IMPORTING
        download.download_path = None
    else:
        download.download_path = "/downloads/album"

    session = _FakeTaskSession(download=download, wishlist=wishlist)

    monkeypatch.setattr(downloads.cfg, "ensure_cache", _noop_async)
    monkeypatch.setattr(downloads, "AsyncSessionLocal", lambda: _SessionFactory(session))
    setup(monkeypatch)

    if scenario == "grab_failure":
        result = await downloads._grab_release_async(download_id=300, guid="g", indexer_id=1)
    else:
        result = await downloads._import_completed_download_async(download_id=300)

    assert assertions(result, download, wishlist)


def test_wishlist_status_badge_values_cover_frontend_states():
    assert WishlistStatus.WANTED.value == "wanted"
    assert WishlistStatus.SEARCHING.value == "searching"
    assert WishlistStatus.FOUND.value == "found"
    assert WishlistStatus.DOWNLOADING.value == "downloading"
    assert WishlistStatus.DOWNLOADED.value == "downloaded"
    assert WishlistStatus.FAILED.value == "failed"
