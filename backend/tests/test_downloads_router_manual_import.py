import pytest
from datetime import datetime
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.models.download import Download, DownloadStatus
from app.routers import downloads as downloads_router
from app.tasks import downloads as downloads_tasks


class _ScalarResult:
    def __init__(self, item):
        self._item = item

    def scalar_one_or_none(self):
        return self._item


class _FakeDb:
    def __init__(self, download):
        self.download = download
        self.committed = 0
        self.refreshed = 0

    async def execute(self, _query):
        return _ScalarResult(self.download)

    async def commit(self):
        self.committed += 1

    async def refresh(self, _model):
        self.refreshed += 1


@pytest.mark.asyncio
async def test_manual_import_requires_source_path():
    fake_db = _FakeDb(Download(id=1, artist_name='A', album_title='B', status=DownloadStatus.FAILED, progress=0.0, source='manual', created_at=datetime.utcnow(), updated_at=datetime.utcnow()))

    async def override_get_db():
        yield fake_db

    app = FastAPI()
    app.include_router(downloads_router.router, prefix='/api/downloads')
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://testserver') as client:
        response = await client.post('/api/downloads/1/import/manual', json={'source_path': ''})

    assert response.status_code == 400
    assert response.json()['detail'] == 'source_path is required'


@pytest.mark.asyncio
async def test_manual_import_rejects_nonexistent_path():
    fake_db = _FakeDb(Download(id=1, artist_name='A', album_title='B', status=DownloadStatus.FAILED, progress=0.0, source='manual', created_at=datetime.utcnow(), updated_at=datetime.utcnow()))

    async def override_get_db():
        yield fake_db

    app = FastAPI()
    app.include_router(downloads_router.router, prefix='/api/downloads')
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://testserver') as client:
        response = await client.post('/api/downloads/1/import/manual', json={'source_path': '/definitely/missing/path'})

    assert response.status_code == 400
    assert response.json()['detail'] == 'source_path does not exist'


@pytest.mark.asyncio
async def test_manual_import_sets_path_and_queues_task(monkeypatch, tmp_path):
    download = Download(id=5, artist_name='A', album_title='B', status=DownloadStatus.COMPLETED, progress=100.0, source='manual', created_at=datetime.utcnow(), updated_at=datetime.utcnow())
    fake_db = _FakeDb(download)
    queued = {}

    async def override_get_db():
        yield fake_db

    def fake_delay(**kwargs):
        queued.update(kwargs)

    monkeypatch.setattr(downloads_tasks.import_completed_download, 'delay', fake_delay)

    app = FastAPI()
    app.include_router(downloads_router.router, prefix='/api/downloads')
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://testserver') as client:
        response = await client.post('/api/downloads/5/import/manual', json={'source_path': str(tmp_path)})

    assert response.status_code == 200
    assert download.download_path == str(tmp_path)
    assert download.status == DownloadStatus.IMPORTING
    assert download.status_message == 'Manual import queued'
    assert queued == {'download_id': 5}
    assert fake_db.committed == 1
    assert fake_db.refreshed == 1
