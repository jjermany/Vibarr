from datetime import datetime

import pytest
from fastapi import HTTPException

from app.routers import auth


class _FakeResult:
    def __init__(self, scalar_value=None, scalar_one_or_none_value=None):
        self._scalar_value = scalar_value
        self._scalar_one_or_none_value = scalar_one_or_none_value

    def scalar(self):
        return self._scalar_value

    def scalar_one_or_none(self):
        return self._scalar_one_or_none_value


class _FakeSession:
    def __init__(self, execute_results):
        self._execute_results = list(execute_results)
        self.added_user = None
        self.committed = False
        self.refreshed = False

    async def execute(self, _query):
        if not self._execute_results:
            raise AssertionError("Unexpected extra db.execute() call")
        return self._execute_results.pop(0)

    def add(self, user):
        self.added_user = user

    async def commit(self):
        self.committed = True

    async def refresh(self, user):
        self.refreshed = True
        user.id = 1
        user.created_at = datetime.utcnow()


@pytest.mark.asyncio
async def test_register_blocked_when_registration_disabled(monkeypatch):
    async def fake_ensure_cache(_db):
        return None

    monkeypatch.setattr(auth.cfg, "ensure_cache", fake_ensure_cache)
    monkeypatch.setattr(auth.cfg, "get_bool", lambda key, default=False: False)
    monkeypatch.setattr(auth.cfg, "get_int", lambda key, default=0: 10)

    db = _FakeSession([])
    request = auth.RegisterRequest(
        username="newuser",
        email="newuser@example.com",
        password="password123",
    )

    with pytest.raises(HTTPException) as exc_info:
        await auth.register(request, db)

    assert exc_info.value.status_code == 403
    assert "disabled" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_register_blocked_at_max_user_count(monkeypatch):
    async def fake_ensure_cache(_db):
        return None

    monkeypatch.setattr(auth.cfg, "ensure_cache", fake_ensure_cache)
    monkeypatch.setattr(auth.cfg, "get_bool", lambda key, default=False: True)
    monkeypatch.setattr(auth.cfg, "get_int", lambda key, default=0: 2)

    db = _FakeSession(
        [
            _FakeResult(scalar_value=2),  # active users
            _FakeResult(scalar_value=2),  # total users
        ]
    )
    request = auth.RegisterRequest(
        username="newuser",
        email="newuser@example.com",
        password="password123",
    )

    with pytest.raises(HTTPException) as exc_info:
        await auth.register(request, db)

    assert exc_info.value.status_code == 403
    assert "maximum user limit" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_register_allowed_within_user_policy(monkeypatch):
    async def fake_ensure_cache(_db):
        return None

    monkeypatch.setattr(auth.cfg, "ensure_cache", fake_ensure_cache)
    monkeypatch.setattr(auth.cfg, "get_bool", lambda key, default=False: True)
    monkeypatch.setattr(auth.cfg, "get_int", lambda key, default=0: 5)
    monkeypatch.setattr(auth, "get_password_hash", lambda raw: f"hashed::{raw}")
    monkeypatch.setattr(auth, "create_access_token", lambda data: f"token::{data['sub']}")

    db = _FakeSession(
        [
            _FakeResult(scalar_value=1),  # active users
            _FakeResult(scalar_value=1),  # total users
            _FakeResult(scalar_one_or_none_value=None),  # existing user check
        ]
    )
    request = auth.RegisterRequest(
        username="newuser",
        email="newuser@example.com",
        password="password123",
    )

    response = await auth.register(request, db)

    assert response.access_token == "token::1"
    assert response.user["username"] == "newuser"
    assert response.user["is_admin"] is False
    assert db.added_user is not None
    assert db.committed is True
    assert db.refreshed is True
