import pytest

from app.services.download_client import DownloadClientService


class _Response:
    def __init__(self, status_code: int, text: str):
        self.status_code = status_code
        self.text = text


class _FakeClient:
    def __init__(self, response: _Response):
        self._response = response

    async def post(self, _path, data=None):
        return self._response


@pytest.mark.asyncio
@pytest.mark.parametrize("body", ["Ok.", "Ok.\n", "ok", "OK! done"])
async def test_authenticate_accepts_normalized_ok(monkeypatch, body):
    service = DownloadClientService()
    service._client = _FakeClient(_Response(200, body))

    monkeypatch.setattr(
        "app.services.download_client.cfg.get_setting",
        lambda _key, default="": default,
    )

    assert await service._authenticate() is True
    assert service._authenticated is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "body"),
    [
        (200, "Fails."),
        (401, "Ok."),
    ],
)
async def test_authenticate_rejects_non_ok_or_non_200(monkeypatch, status_code, body):
    service = DownloadClientService()
    service._client = _FakeClient(_Response(status_code, body))

    monkeypatch.setattr(
        "app.services.download_client.cfg.get_setting",
        lambda _key, default="": default,
    )

    assert await service._authenticate() is False


@pytest.mark.asyncio
@pytest.mark.parametrize("body", ["Ok.", "Ok.\n", "OK Added"])
async def test_add_torrent_url_accepts_normalized_ok(monkeypatch, body):
    service = DownloadClientService()

    async def _fake_get_client():
        return _FakeClient(_Response(200, body))

    monkeypatch.setattr(service, "_get_client", _fake_get_client)
    monkeypatch.setattr(
        "app.services.download_client.cfg.get_setting",
        lambda _key, default="": default,
    )

    assert await service.add_torrent_url("magnet:?xt=urn:btih:abc") is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "body"),
    [
        (200, "Queued"),
        (500, "Ok."),
    ],
)
async def test_add_torrent_url_rejects_non_ok_or_non_200(monkeypatch, status_code, body):
    service = DownloadClientService()

    async def _fake_get_client():
        return _FakeClient(_Response(status_code, body))

    monkeypatch.setattr(service, "_get_client", _fake_get_client)
    monkeypatch.setattr(
        "app.services.download_client.cfg.get_setting",
        lambda _key, default="": default,
    )

    assert await service.add_torrent_url("magnet:?xt=urn:btih:abc") is False
