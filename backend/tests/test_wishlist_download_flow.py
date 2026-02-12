import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.sql.dml import Update

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
        self.commit_count = 0

    async def execute(self, _query):
        return _ScalarResult(self.item)

    async def commit(self):
        self.commit_count += 1

    async def delete(self, _model):
        return None




class _ScalarsListResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items


class _FakeRouterDbMany:
    def __init__(self, items):
        self.items = items
        self.commit_count = 0

    async def execute(self, _query):
        return _ScalarsListResult(self.items)

    async def commit(self):
        self.commit_count += 1


class _FakeRouterDeleteDb:
    def __init__(self, item, downloads):
        self.item = item
        self.downloads = downloads
        self.deleted = []
        self.commit_count = 0

    async def execute(self, query):
        if isinstance(query, Update):
            for download in self.downloads:
                if download.wishlist_id == self.item.id:
                    download.wishlist_id = None
            return None
        return _ScalarResult(self.item)

    async def delete(self, model):
        self.deleted.append(model)
        self.item = None

    async def commit(self):
        self.commit_count += 1

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
    assert item.status == WishlistStatus.SEARCHING
    assert item.last_searched_at is not None
    assert item.search_count == 1
    assert fake_db.commit_count == 1


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


@pytest.mark.asyncio
async def test_post_search_all_marks_wanted_items_searching_before_queue(monkeypatch):
    items = [
        WishlistItem(id=1, item_type="album", status=WishlistStatus.WANTED, search_count=0),
        WishlistItem(id=2, item_type="artist", status=WishlistStatus.WANTED, search_count=2),
    ]
    fake_db = _FakeRouterDbMany(items)
    queued = {}

    async def override_get_db():
        yield fake_db

    def fake_delay(**kwargs):
        queued.update(kwargs)

    monkeypatch.setattr(wishlist_router, "prowlarr_service", type("_Svc", (), {"is_available": True})())
    monkeypatch.setattr(downloads.process_wishlist, "delay", fake_delay)

    app = FastAPI()
    app.include_router(wishlist_router.router, prefix="/api/wishlist")
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post("/api/wishlist/search-all")

    assert response.status_code == 200
    assert response.json() == {"status": "search_all_queued", "items_to_search": 2}
    assert queued == {"search_all": True}
    assert fake_db.commit_count == 1
    assert all(item.status == WishlistStatus.SEARCHING for item in items)
    assert all(item.last_searched_at is not None for item in items)
    assert [item.search_count for item in items] == [1, 3]


@pytest.mark.asyncio
async def test_delete_wishlist_item_wanted_status_returns_stable_payload():
    item = WishlistItem(id=77, item_type="album", status=WishlistStatus.WANTED)
    fake_db = _FakeRouterDeleteDb(item=item, downloads=[])

    async def override_get_db():
        yield fake_db

    app = FastAPI()
    app.include_router(wishlist_router.router, prefix="/api/wishlist")
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.delete("/api/wishlist/77")

    assert response.status_code == 200
    assert response.json() == {"status": "deleted", "id": 77}
    assert fake_db.commit_count == 1


@pytest.mark.asyncio
async def test_delete_found_wishlist_item_detaches_related_downloads():
    item = WishlistItem(id=88, item_type="album", status=WishlistStatus.FOUND)
    linked_download = Download(
        id=501,
        wishlist_id=88,
        artist_name="Artist",
        album_title="Album",
        status=DownloadStatus.FOUND,
    )
    unlinked_download = Download(
        id=502,
        wishlist_id=999,
        artist_name="Other",
        album_title="Other Album",
        status=DownloadStatus.FOUND,
    )
    fake_db = _FakeRouterDeleteDb(item=item, downloads=[linked_download, unlinked_download])

    async def override_get_db():
        yield fake_db

    app = FastAPI()
    app.include_router(wishlist_router.router, prefix="/api/wishlist")
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.delete("/api/wishlist/88")

    assert response.status_code == 200
    assert response.json() == {"status": "deleted", "id": 88}
    assert linked_download.wishlist_id is None
    assert unlinked_download.wishlist_id == 999
    assert fake_db.commit_count == 1


class _FakeBulkWishlistDb:
    def __init__(self, items, downloads=None):
        self.items = {item.id: item for item in items}
        self.downloads = downloads or []
        self.commit_count = 0

    async def execute(self, query):
        if isinstance(query, Update):
            where_value = query.whereclause.right.value
            for download in self.downloads:
                if download.wishlist_id == where_value:
                    download.wishlist_id = None
            return None

        entity = query.column_descriptions[0].get("entity")
        if entity is WishlistItem:
            where = query.whereclause
            if where is None:
                return _ScalarsListResult(list(self.items.values()))

            operator_name = where.operator.__name__
            if operator_name == "in_op":
                values = where.right.value
                return _ScalarsListResult([self.items[item_id] for item_id in values if item_id in self.items])
            if operator_name == "eq":
                value = where.right.value
                if isinstance(value, WishlistStatus):
                    return _ScalarsListResult([item for item in self.items.values() if item.status == value])
                return _ScalarResult(self.items.get(value))

        return _ScalarsListResult([])

    async def delete(self, model):
        self.items.pop(model.id, None)

    async def commit(self):
        self.commit_count += 1


@pytest.mark.asyncio
async def test_search_selected_wishlist_mixed_results(monkeypatch):
    wanted = WishlistItem(id=10, item_type="album", status=WishlistStatus.WANTED)
    found = WishlistItem(id=11, item_type="album", status=WishlistStatus.FOUND)
    fake_db = _FakeBulkWishlistDb([wanted, found])
    queued_ids = []

    async def override_get_db():
        yield fake_db

    def fake_delay(item_id):
        queued_ids.append(item_id)

    monkeypatch.setattr(wishlist_router, "prowlarr_service", type("_Svc", (), {"is_available": True})())
    monkeypatch.setattr(downloads.search_wishlist_item, "delay", fake_delay)

    app = FastAPI()
    app.include_router(wishlist_router.router, prefix="/api/wishlist")
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post("/api/wishlist/search-selected", json={"item_ids": [10, 11, 999]})

    assert response.status_code == 200
    assert response.json() == {
        "requested": 3,
        "queued": 1,
        "skipped": 1,
        "failed": 1,
        "queued_ids": [10],
        "skipped_ids": [11],
        "failed_ids": [999],
    }
    assert queued_ids == [10]
    assert wanted.status == WishlistStatus.SEARCHING
    assert fake_db.commit_count == 1


@pytest.mark.asyncio
async def test_bulk_delete_selected_returns_counts_and_cleans_download_refs():
    item_one = WishlistItem(id=21, item_type="album", status=WishlistStatus.WANTED)
    item_two = WishlistItem(id=22, item_type="artist", status=WishlistStatus.FOUND)
    linked_download = Download(id=300, wishlist_id=21, artist_name="Artist", album_title="Album")
    fake_db = _FakeBulkWishlistDb([item_one, item_two], downloads=[linked_download])

    async def override_get_db():
        yield fake_db

    app = FastAPI()
    app.include_router(wishlist_router.router, prefix="/api/wishlist")
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.request(
            "DELETE",
            "/api/wishlist/bulk",
            json={"item_ids": [21, 404]},
        )

    assert response.status_code == 200
    assert response.json() == {
        "requested": 2,
        "deleted": 1,
        "skipped": 0,
        "failed": 1,
        "deleted_ids": [21],
        "skipped_ids": [],
        "failed_ids": [404],
    }
    assert linked_download.wishlist_id is None
    assert fake_db.commit_count == 1


@pytest.mark.asyncio
async def test_bulk_delete_all_with_status_filter():
    wanted = WishlistItem(id=31, item_type="album", status=WishlistStatus.WANTED)
    found = WishlistItem(id=32, item_type="album", status=WishlistStatus.FOUND)
    fake_db = _FakeBulkWishlistDb([wanted, found])

    async def override_get_db():
        yield fake_db

    app = FastAPI()
    app.include_router(wishlist_router.router, prefix="/api/wishlist")
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.request(
            "DELETE",
            "/api/wishlist/bulk",
            json={"all": True, "status": "wanted"},
        )

    assert response.status_code == 200
    assert response.json()["deleted_ids"] == [31]
    assert 31 not in fake_db.items
    assert 32 in fake_db.items
