import pytest
from sqlalchemy.exc import DBAPIError

from app import database


class _FakeConnection:
    async def run_sync(self, _fn):
        return None


class _FakeBeginContext:
    def __init__(self, behavior):
        self.behavior = behavior

    async def __aenter__(self):
        action = self.behavior()
        if isinstance(action, Exception):
            raise action
        return _FakeConnection()

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeEngine:
    def __init__(self, behavior):
        self._behavior = behavior

    def begin(self):
        return _FakeBeginContext(self._behavior)


@pytest.mark.asyncio
async def test_init_db_retries_full_workflow_then_succeeds(monkeypatch, caplog):
    attempts = {"count": 0}

    def behavior():
        attempts["count"] += 1
        if attempts["count"] < 3:
            return DBAPIError("SELECT 1", {}, Exception("the database system is starting up"))
        return object()

    async def fake_migrations(_conn):
        return None

    sleep_delays = []

    async def fake_sleep(delay):
        sleep_delays.append(delay)

    monkeypatch.setattr(database, "engine", _FakeEngine(behavior))
    monkeypatch.setattr(database, "_apply_schema_migrations", fake_migrations)
    monkeypatch.setattr(database.asyncio, "sleep", fake_sleep)

    caplog.set_level("WARNING")

    await database.init_db()

    assert attempts["count"] == 3
    assert sleep_delays == [1.0, 2.0]
    assert sum("Database initialization attempt failed; retrying" in msg for msg in caplog.messages) == 2


@pytest.mark.asyncio
async def test_init_db_raises_after_final_attempt(monkeypatch):
    attempts = {"count": 0}

    original_exception = DBAPIError("SELECT 1", {}, Exception("the database system is starting up"))

    def behavior():
        attempts["count"] += 1
        return original_exception

    async def fake_migrations(_conn):
        return None

    async def fake_sleep(_delay):
        return None

    monkeypatch.setattr(database, "engine", _FakeEngine(behavior))
    monkeypatch.setattr(database, "_apply_schema_migrations", fake_migrations)
    monkeypatch.setattr(database.asyncio, "sleep", fake_sleep)

    with pytest.raises(DBAPIError) as raised:
        await database.init_db()

    assert attempts["count"] == 30
    assert raised.value is original_exception
