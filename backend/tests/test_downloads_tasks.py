import asyncio
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
                    "download_url": "https://example.com/a.torrent",
                }
            ]
        ),
    )
    monkeypatch.setattr(downloads, "AsyncSessionLocal", lambda: _SessionFactory(session))
    monkeypatch.setattr(downloads.cfg, "get_bool", lambda *args, **kwargs: False)
    monkeypatch.setattr(downloads.grab_release, "delay", lambda **kwargs: None)

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
async def test_search_wishlist_item_always_grabs_on_manual_search(monkeypatch):
    """User-initiated search always grabs the best result regardless of settings."""
    item = WishlistItem(
        id=3,
        item_type="album",
        artist_name="Artist",
        album_title="Album",
        status=WishlistStatus.WANTED,
        search_count=0,
        auto_download=False,
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
                    "score": 10,
                    "guid": "release-guid",
                    "protocol": "torrent",
                    "download_url": "https://example.com/release.torrent",
                }
            ]
        ),
    )
    monkeypatch.setattr(downloads, "AsyncSessionLocal", lambda: _SessionFactory(session))

    def fake_delay(**kwargs):
        grabbed.update(kwargs)

    # auto_download_enabled is False — grab should still happen
    monkeypatch.setattr(downloads.cfg, "get_bool", lambda *args, **kwargs: False)
    monkeypatch.setattr(downloads.grab_release, "delay", fake_delay)

    payload = await downloads._search_wishlist_item_async(item_id=3)

    assert payload["status"] == "found"
    assert payload["download_id"] == 999
    assert grabbed == {
        "download_id": 999,
        "guid": "release-guid",
        "indexer_id": 7,
        "protocol": "torrent",
        "download_url": "https://example.com/release.torrent",
        "release_title": "Artist - Album FLAC",
    }


class _ScalarsResult:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class _ListResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return _ScalarsResult(self._items)


class _FakeMultiSession:
    def __init__(self, download=None, wishlist=None, active_downloads=None):
        self.download = download
        self.wishlist = wishlist
        self.active_downloads = active_downloads or ([] if download is None else [download])

    async def execute(self, query):
        entity = query.column_descriptions[0].get("entity")
        if entity is WishlistItem:
            return _ScalarResult(self.wishlist)
        if entity.__name__ == "Download":
            if any("status" in str(c) for c in query._where_criteria):
                return _ListResult(self.active_downloads)
            return _ScalarResult(self.download)
        return _ScalarResult(None)

    def add(self, model):
        return None

    async def commit(self):
        return None

    async def refresh(self, model):
        return None


class _FakeTorrent:
    def __init__(self, *, is_complete=False, is_errored=False, state="", progress=0.0, dl_speed=0, eta=0, content_path="/music/final", save_path="/music"):
        self.is_complete = is_complete
        self.is_errored = is_errored
        self.state = state
        self.progress = progress
        self.dl_speed = dl_speed
        self.eta = eta
        self.content_path = content_path
        self.save_path = save_path


class _FakeClientForStatus:
    def __init__(self, torrent):
        self.is_configured = True
        self._torrent = torrent

    async def get_torrent(self, _download_id):
        return self._torrent

    async def delete_torrent(self, _download_id, delete_files=False):
        return None

    async def find_torrent_hash(self, release_title, timeout_seconds=1, poll_interval_seconds=0.5):
        return None


class _ImportResult:
    def __init__(self, success, error=None):
        self.success = success
        self.error = error
        self.albums_imported = 1
        self.tracks_imported = 10
        self.final_path = "/library/artist/album"


class _FakeBeetsService:
    def __init__(self, result):
        self.is_available = True
        self._result = result

    async def import_directory(self, **_kwargs):
        return self._result




class _FakeDirectDownloadClient:
    def __init__(self, *, add_success=True, torrent_hash=None, is_configured=True):
        self.is_configured = is_configured
        self._add_success = add_success
        self._torrent_hash = torrent_hash

    async def add_torrent_url(self, _download_url):
        return self._add_success

    async def find_torrent_hash(self, release_title):
        return self._torrent_hash


class _FakeSabService:
    def __init__(self, *, is_configured=False, nzo_id=None):
        self.is_configured = is_configured
        self._nzo_id = nzo_id

    async def add_nzb_url(self, _download_url, name=None):
        return self._nzo_id

class _FakeProwlarrGrabService:
    def __init__(self, grab_result):
        self.is_available = True
        self._grab_result = grab_result

    async def grab(self, *_args, **_kwargs):
        if isinstance(self._grab_result, dict):
            return self._grab_result
        return {"success": bool(self._grab_result), "download_id": self._grab_result}


@pytest.mark.asyncio
async def test_status_transition_downloading_to_importing_to_downloaded(monkeypatch):
    wishlist = WishlistItem(id=10, item_type="album", status=WishlistStatus.DOWNLOADING)
    download = downloads.Download(
        id=100,
        artist_name="Artist",
        album_title="Album",
        status=DownloadStatus.DOWNLOADING,
        download_id="hash",
        wishlist_id=10,
    )
    session = _FakeMultiSession(download=download, wishlist=wishlist)

    monkeypatch.setattr(downloads.cfg, "ensure_cache", _noop_async)
    monkeypatch.setattr(downloads, "AsyncSessionLocal", lambda: _SessionFactory(session))
    monkeypatch.setattr(downloads, "download_client_service", _FakeClientForStatus(_FakeTorrent(is_complete=True, progress=100.0)))
    monkeypatch.setattr(downloads.cfg, "get_setting", lambda *args, **kwargs: "/music/completed")

    def fake_get_bool(key, default=False):
        mapping = {
            "beets_enabled": True,
            "beets_auto_import": True,
            "qbittorrent_remove_completed": False,
            "sabnzbd_remove_completed": False,
        }
        return mapping.get(key, default)

    monkeypatch.setattr(downloads.cfg, "get_bool", fake_get_bool)
    monkeypatch.setattr(downloads.import_completed_download, "delay", lambda **kwargs: None)

    payload = await downloads._check_download_status_async()

    assert payload["completed"] == 1
    assert download.status == DownloadStatus.IMPORTING
    assert wishlist.status == WishlistStatus.IMPORTING

    monkeypatch.setattr(
        downloads,
        "beets_service",
        _FakeBeetsService(_ImportResult(success=True)),
    )

    result = await downloads._import_completed_download_async(download_id=100)

    assert result["status"] == "completed"
    assert download.status == DownloadStatus.COMPLETED
    assert wishlist.status == WishlistStatus.DOWNLOADED


@pytest.mark.asyncio
async def test_grab_or_import_failures_mark_wishlist_failed(monkeypatch):
    wishlist = WishlistItem(id=20, item_type="album", status=WishlistStatus.FOUND)
    download = downloads.Download(
        id=200,
        artist_name="Artist",
        album_title="Album",
        status=DownloadStatus.FOUND,
        wishlist_id=20,
        download_id="hash",
        download_path="/downloads/album",
    )
    session = _FakeMultiSession(download=download, wishlist=wishlist)

    monkeypatch.setattr(downloads.cfg, "ensure_cache", _noop_async)
    monkeypatch.setattr(downloads, "AsyncSessionLocal", lambda: _SessionFactory(session))
    monkeypatch.setattr(
        downloads,
        "download_client_service",
        _FakeDirectDownloadClient(add_success=False),
    )

    grab_result = await downloads._grab_release_async(
        download_id=200,
        guid="g",
        indexer_id=1,
        protocol="torrent",
        download_url="https://example.com/a.torrent",
        release_title="Artist - Album",
    )

    assert grab_result["status"] == "error"
    assert download.status == DownloadStatus.FAILED
    assert wishlist.status == WishlistStatus.FAILED
    assert "qBittorrent URL add failed" in (wishlist.notes or "")

    wishlist.status = WishlistStatus.DOWNLOADING
    download.status = DownloadStatus.IMPORTING

    monkeypatch.setattr(
        downloads,
        "beets_service",
        _FakeBeetsService(_ImportResult(success=False, error="bad tags")),
    )

    import_result = await downloads._import_completed_download_async(download_id=200)

    assert import_result["status"] == "completed"
    assert download.status == DownloadStatus.FAILED
    assert wishlist.status == WishlistStatus.FAILED
    assert "Beets import failed" in (wishlist.notes or "")




@pytest.mark.asyncio
async def test_grab_ack_without_client_id_stays_queued(monkeypatch):
    wishlist = WishlistItem(id=21, item_type="album", status=WishlistStatus.FOUND)
    download = downloads.Download(
        id=201,
        artist_name="Artist",
        album_title="Album",
        status=DownloadStatus.FOUND,
        wishlist_id=21,
    )
    session = _FakeMultiSession(download=download, wishlist=wishlist)

    monkeypatch.setattr(downloads.cfg, "ensure_cache", _noop_async)
    monkeypatch.setattr(downloads, "AsyncSessionLocal", lambda: _SessionFactory(session))
    monkeypatch.setattr(
        downloads,
        "download_client_service",
        _FakeDirectDownloadClient(add_success=True, torrent_hash=None),
    )

    grab_result = await downloads._grab_release_async(
        download_id=201,
        guid="g",
        indexer_id=1,
        protocol="torrent",
        download_url="https://example.com/a.torrent",
        release_title="Artist - Album",
    )

    assert grab_result["status"] == "grabbed"
    assert grab_result["client_id"] is None
    assert download.status == DownloadStatus.QUEUED
    assert download.status_message == "Queued; waiting for qBittorrent hash"
    assert wishlist.status == WishlistStatus.DOWNLOADING




@pytest.mark.asyncio
async def test_grab_torrent_prefers_prowlarr_before_direct_url(monkeypatch):
    wishlist = WishlistItem(id=24, item_type="album", status=WishlistStatus.FOUND)
    download = downloads.Download(
        id=204,
        artist_name="Artist",
        album_title="Album",
        status=DownloadStatus.FOUND,
        wishlist_id=24,
    )
    session = _FakeMultiSession(download=download, wishlist=wishlist)

    monkeypatch.setattr(downloads.cfg, "ensure_cache", _noop_async)
    monkeypatch.setattr(downloads, "AsyncSessionLocal", lambda: _SessionFactory(session))
    monkeypatch.setattr(downloads, "prowlarr_service", _FakeProwlarrGrabService({"success": True, "download_id": "p-123"}))

    class _ShouldNotBeUsedClient:
        is_configured = True

        async def add_torrent_url(self, _download_url):
            raise AssertionError("Direct URL fallback should not run when Prowlarr succeeds")

        async def find_torrent_hash(self, release_title):
            return None

    monkeypatch.setattr(downloads, "download_client_service", _ShouldNotBeUsedClient())

    result = await downloads._grab_release_async(
        download_id=204,
        guid="g-1",
        indexer_id=11,
        protocol="torrent",
        download_url="https://example.com/a.torrent",
        release_title="Artist - Album",
    )

    assert result["status"] == "grabbed"
    assert result["client_id"] == "p-123"
    assert download.status == DownloadStatus.DOWNLOADING
    assert download.status_message is None
    assert wishlist.status == WishlistStatus.DOWNLOADING


@pytest.mark.asyncio
async def test_grab_torrent_falls_back_to_direct_url_after_prowlarr_failure(monkeypatch):
    wishlist = WishlistItem(id=25, item_type="album", status=WishlistStatus.FOUND)
    download = downloads.Download(
        id=205,
        artist_name="Artist",
        album_title="Album",
        status=DownloadStatus.FOUND,
        wishlist_id=25,
    )
    session = _FakeMultiSession(download=download, wishlist=wishlist)

    monkeypatch.setattr(downloads.cfg, "ensure_cache", _noop_async)
    monkeypatch.setattr(downloads, "AsyncSessionLocal", lambda: _SessionFactory(session))
    monkeypatch.setattr(downloads, "prowlarr_service", _FakeProwlarrGrabService({"success": False, "download_id": None}))
    monkeypatch.setattr(downloads, "download_client_service", _FakeDirectDownloadClient(add_success=True, torrent_hash="hash-205"))

    result = await downloads._grab_release_async(
        download_id=205,
        guid="g-2",
        indexer_id=12,
        protocol="torrent",
        download_url="https://example.com/b.torrent",
        release_title="Artist - Album",
    )

    assert result["status"] == "grabbed"
    assert result["client_id"] == "hash-205"
    assert download.status == DownloadStatus.DOWNLOADING
    assert wishlist.status == WishlistStatus.DOWNLOADING


@pytest.mark.asyncio
async def test_check_status_marks_missing_qbit_registration_failed_after_timeout(monkeypatch):
    wishlist = WishlistItem(id=23, item_type="album", status=WishlistStatus.DOWNLOADING)
    download = downloads.Download(
        id=203,
        artist_name="Artist",
        album_title="Album",
        release_title="Artist - Album",
        status=DownloadStatus.DOWNLOADING,
        started_at=downloads.datetime.utcnow() - downloads.timedelta(minutes=4),
        wishlist_id=23,
        download_client="qbittorrent",
    )
    session = _FakeMultiSession(download=download, wishlist=wishlist)

    monkeypatch.setattr(downloads.cfg, "ensure_cache", _noop_async)
    monkeypatch.setattr(downloads, "AsyncSessionLocal", lambda: _SessionFactory(session))
    monkeypatch.setattr(downloads, "download_client_service", _FakeClientForStatus(None))

    payload = await downloads._check_download_status_async()

    assert payload["updated"] == 1
    assert download.status == DownloadStatus.FAILED
    assert "hash resolution timed out" in (download.status_message or "")
    assert wishlist.status == WishlistStatus.FAILED


def _new_value_coro(value):
    async def _inner():
        return value

    return _inner()


def test_run_async_reuses_persistent_worker_loop(monkeypatch):
    class _FakeLoop:
        def __init__(self):
            self.closed = False
            self.run_calls = 0

        def is_closed(self):
            return self.closed

        def run_until_complete(self, coro):
            self.run_calls += 1
            return asyncio.run(coro)

        def close(self):
            self.closed = True

    created_loops = []

    def _make_loop():
        loop = _FakeLoop()
        created_loops.append(loop)
        return loop

    monkeypatch.setattr(downloads.asyncio, "new_event_loop", _make_loop)
    monkeypatch.setattr(downloads.asyncio, "set_event_loop", lambda loop: None)
    monkeypatch.setattr(downloads, "_task_loop", None)

    assert downloads._run_async(_new_value_coro(1)) == 1
    assert downloads._run_async(_new_value_coro(2)) == 2

    assert len(created_loops) == 1
    assert created_loops[0].run_calls == 2
    assert created_loops[0].closed is False


def test_run_async_recreates_closed_loop(monkeypatch):
    class _FakeClosedLoop:
        def is_closed(self):
            return True

    class _FakeLoop:
        def __init__(self):
            self.closed = False

        def is_closed(self):
            return self.closed

        def run_until_complete(self, coro):
            return asyncio.run(coro)

        def close(self):
            self.closed = True

    created_loops = []

    def _make_loop():
        loop = _FakeLoop()
        created_loops.append(loop)
        return loop

    monkeypatch.setattr(downloads.asyncio, "new_event_loop", _make_loop)
    monkeypatch.setattr(downloads.asyncio, "set_event_loop", lambda loop: None)
    monkeypatch.setattr(downloads, "_task_loop", _FakeClosedLoop())

    assert downloads._run_async(_new_value_coro(42)) == 42
    assert len(created_loops) == 1


def test_shutdown_task_loop_closes_resources(monkeypatch):
    events = []

    class _FakeLoop:
        def __init__(self):
            self.closed = False

        def is_closed(self):
            return self.closed

        def run_until_complete(self, coro):
            return asyncio.run(coro)

        def close(self):
            self.closed = True
            events.append("loop_closed")

    async def _fake_close():
        events.append("resources_closed")

    fake_loop = _FakeLoop()
    monkeypatch.setattr(downloads, "_task_loop", fake_loop)
    monkeypatch.setattr(downloads, "_close_task_resources", _fake_close)

    downloads._shutdown_task_loop()

    assert events == ["resources_closed", "loop_closed"]
    assert fake_loop.closed is True
    assert downloads._task_loop is None
