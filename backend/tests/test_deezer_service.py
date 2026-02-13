import pytest
import httpx

from app.services.deezer import DeezerService


def test_log_failure_uses_warning_for_timeout(caplog):
    service = DeezerService()

    with caplog.at_level("WARNING"):
        service._log_failure(
            source="deezer album",
            endpoint_type="search",
            query="dr",
            exc=httpx.ConnectTimeout("timed out"),
        )

    assert "Deezer request failed" in caplog.text
    assert "ConnectTimeout" in caplog.text


def test_request_timeout_prefers_fast_connect_timeout():
    service = DeezerService()

    assert service.REQUEST_TIMEOUT.connect == 2.0
    assert service.REQUEST_TIMEOUT.read == 6.0


@pytest.mark.asyncio
async def test_get_playlist_tracks_follows_next_url(monkeypatch):
    service = DeezerService()

    async def fake_get(path, params=None):
        assert path == "/playlist/123/tracks"
        assert params == {"limit": 2, "index": 0}
        return {
            "data": [{"id": 1}, {"id": 2}],
            "total": 4,
            "next": "https://api.deezer.com/playlist/123/tracks?index=2&limit=2",
        }

    async def fake_get_by_url(url):
        assert "index=2" in url
        return {"data": [{"id": 3}, {"id": 4}], "total": 4}

    monkeypatch.setattr(service, "_get", fake_get)
    monkeypatch.setattr(service, "_get_by_url", fake_get_by_url)

    tracks = await service.get_playlist_tracks("123", limit=2)

    assert [track["id"] for track in tracks] == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_get_playlist_tracks_uses_offset_when_next_missing(monkeypatch):
    service = DeezerService()
    calls = []

    async def fake_get(path, params=None):
        calls.append((path, params))
        if params["index"] == 0:
            return {"data": [{"id": 1}, {"id": 2}], "total": 3}
        return {"data": [{"id": 3}], "total": 3}

    monkeypatch.setattr(service, "_get", fake_get)

    tracks = await service.get_playlist_tracks("321", limit=2)

    assert [track["id"] for track in tracks] == [1, 2, 3]
    assert calls == [
        ("/playlist/321/tracks", {"limit": 2, "index": 0}),
        ("/playlist/321/tracks", {"limit": 2, "index": 2}),
    ]


@pytest.mark.asyncio
async def test_get_playlist_with_tracks_replaces_embedded_tracks(monkeypatch):
    service = DeezerService()

    async def fake_get_playlist(playlist_id):
        assert playlist_id == "7"
        return {
            "id": 7,
            "title": "Playlist",
            "tracks": {"data": [{"id": 1}], "next": "https://api.deezer.com/x?index=1"},
        }

    async def fake_get_playlist_tracks(playlist_id, limit=100):
        assert playlist_id == "7"
        assert limit == 100
        return [{"id": 1}, {"id": 2}]

    monkeypatch.setattr(service, "get_playlist", fake_get_playlist)
    monkeypatch.setattr(service, "get_playlist_tracks", fake_get_playlist_tracks)

    playlist = await service.get_playlist_with_tracks("7")

    assert playlist["tracks"]["data"] == [{"id": 1}, {"id": 2}]
    assert playlist["tracks"]["total"] == 2
    assert "next" not in playlist["tracks"]
