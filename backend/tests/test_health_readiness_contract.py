import sys

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.routers import health


class _DbSession:
    def __init__(self, healthy: bool):
        self.healthy = healthy

    async def execute(self, _query):
        if not self.healthy:
            raise RuntimeError("db unavailable")
        return 1


class _RedisClient:
    def __init__(self, healthy: bool):
        self.healthy = healthy

    def ping(self):
        if not self.healthy:
            raise RuntimeError("redis unavailable")
        return True


class _RedisModule:
    def __init__(self, healthy: bool):
        self.healthy = healthy

    def from_url(self, _url):
        return _RedisClient(self.healthy)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("db_ok", "redis_ok", "expected_status", "expected_api_usable"),
    [
        (True, True, "ready", True),
        (True, False, "degraded", True),
        (False, True, "degraded", False),
        (False, False, "degraded", False),
    ],
)
async def test_health_ready_contract_db_minimum_vs_strict_ready(
    monkeypatch, db_ok, redis_ok, expected_status, expected_api_usable
):
    app = FastAPI()
    app.include_router(health.router)

    async def override_get_db():
        yield _DbSession(db_ok)

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setitem(sys.modules, "redis", _RedisModule(redis_ok))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/health/ready")

    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == expected_status
    assert payload["checks"] == {"database": db_ok, "redis": redis_ok}

    # Frontend contract in useBackendReadiness.isApiUsable:
    # checks.database=true is sufficient (DB-minimum), while backendReady is strict status=ready.
    backend_ready = payload["status"] == "ready"
    api_usable = payload["checks"].get("database") is True or payload["status"] == "ready"

    assert backend_ready is (expected_status == "ready")
    assert api_usable is expected_api_usable
