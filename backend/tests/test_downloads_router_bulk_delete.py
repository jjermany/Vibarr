import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.models.download import Download, DownloadStatus
from app.routers import downloads as downloads_router


class _ScalarsResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items


class _FakeDb:
    def __init__(self, downloads):
        self.downloads = downloads
        self.deleted = []
        self.committed = 0

    async def execute(self, _query):
        return _ScalarsResult(self.downloads)

    async def delete(self, model):
        self.deleted.append(model.id)

    async def commit(self):
        self.committed += 1


class _DownloadClient:
    is_configured = True

    def __init__(self):
        self.deleted = []

    async def delete_torrent(self, download_id, delete_files=True):
        self.deleted.append((download_id, delete_files))


@pytest.mark.asyncio
async def test_bulk_delete_selected_downloads_removes_requested_items(monkeypatch):
    active = Download(id=10, artist_name='A', album_title='X', status=DownloadStatus.DOWNLOADING, download_id='hash-10')
    history = Download(id=20, artist_name='B', album_title='Y', status=DownloadStatus.COMPLETED, download_id=None)
    fake_db = _FakeDb([active, history])
    fake_client = _DownloadClient()

    async def override_get_db():
        yield fake_db

    monkeypatch.setattr(downloads_router, 'download_client_service', fake_client)

    app = FastAPI()
    app.include_router(downloads_router.router, prefix='/api/downloads')
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://testserver') as client:
        response = await client.request('DELETE', '/api/downloads/bulk/delete', json={'download_ids': [10, 20]})

    assert response.status_code == 200
    payload = response.json()
    assert payload['deleted'] == 2
    assert payload['failed'] == 0
    assert set(payload['deleted_ids']) == {10, 20}
    assert set(fake_db.deleted) == {10, 20}
    assert fake_db.committed == 1
    assert fake_client.deleted == [('hash-10', True)]


@pytest.mark.asyncio
async def test_bulk_delete_requires_ids_when_not_deleting_all():
    fake_db = _FakeDb([])

    async def override_get_db():
        yield fake_db

    app = FastAPI()
    app.include_router(downloads_router.router, prefix='/api/downloads')
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://testserver') as client:
        response = await client.request('DELETE', '/api/downloads/bulk/delete', json={'download_ids': []})

    assert response.status_code == 400
    assert response.json()['detail'] == 'download_ids required when all=false'
