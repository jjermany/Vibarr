import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.models.user import User
from app.routers.settings import router as settings_router
from app.database import get_db
from app.services.auth import require_admin


@pytest.mark.asyncio
async def test_get_download_settings_requires_authentication():
    app = FastAPI()
    app.include_router(settings_router, prefix="/api/settings")

    async def override_get_db():
        yield object()

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/api/settings/download")

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required"


@pytest.mark.asyncio
async def test_get_download_settings_returns_payload_for_admin(monkeypatch):
    app = FastAPI()
    app.include_router(settings_router, prefix="/api/settings")

    async def override_get_db():
        yield object()

    async def override_require_admin():
        return User(id=1, username="admin", email="admin@example.com", is_admin=True)

    async def fake_ensure_cache(_db):
        return None

    values = {
        "auto_download_enabled": True,
        "auto_download_confidence_threshold": 0.9,
        "preferred_quality": "320",
        "max_concurrent_downloads": 5,
        "download_path": "/downloads/custom",
        "completed_download_path": "/media/custom-completed",
    }

    monkeypatch.setattr("app.routers.settings.cfg.ensure_cache", fake_ensure_cache)
    monkeypatch.setattr(
        "app.routers.settings.cfg.get_bool",
        lambda key, default=False: values.get(key, default),
    )
    monkeypatch.setattr(
        "app.routers.settings.cfg.get_float",
        lambda key, default=0.0: values.get(key, default),
    )
    monkeypatch.setattr(
        "app.routers.settings.cfg.get_setting",
        lambda key, default="": values.get(key, default),
    )
    monkeypatch.setattr(
        "app.routers.settings.cfg.get_int",
        lambda key, default=0: values.get(key, default),
    )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_admin] = override_require_admin

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/api/settings/download")

    assert response.status_code == 200
    assert response.json() == values
