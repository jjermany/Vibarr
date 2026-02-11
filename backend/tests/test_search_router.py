import asyncio

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.routers import search as search_router
from app.database import get_db


def test_deezer_image_from_payload_uses_md5_fallback():
    payload = {"md5_image": "abc123"}

    image_url = search_router._deezer_image_from_payload(payload, "album")

    assert (
        image_url
        == "https://e-cdns-images.dzcdn.net/images/album/abc123/1000x1000-000000-80-0-0.jpg"
    )


def test_search_models_do_not_share_mutable_defaults():
    first_item = search_router.SearchResultItem(
        id="1", type="artist", name="first", source="local"
    )
    second_item = search_router.SearchResultItem(
        id="2", type="artist", name="second", source="local"
    )

    first_item.external_ids["spotify_id"] = "abc"

    assert second_item.external_ids == {}

    first_response = search_router.SearchResponse(query="q", total=0)
    second_response = search_router.SearchResponse(query="q", total=0)

    first_response.artists.append(first_item)
    first_response.albums.append(first_item)
    first_response.tracks.append(first_item)

    assert second_response.artists == []
    assert second_response.albums == []
    assert second_response.tracks == []

    first_preview = search_router.PreviewResponse(type="artist", name="first")
    second_preview = search_router.PreviewResponse(type="artist", name="second")

    first_preview.tags.append("rock")
    first_preview.top_albums.append({"name": "best of"})
    first_preview.tracks.append({"name": "track 1"})

    assert second_preview.tags == []
    assert second_preview.top_albums == []
    assert second_preview.tracks == []


@pytest.mark.asyncio
async def test_search_deezer_tracks_populates_image_and_external_ids(monkeypatch):
    async def fake_search_tracks(_query: str, limit: int = 20):
        assert limit == 3
        return [
            {
                "id": 42,
                "title": "No Cover Track",
                "artist": {
                    "id": 7,
                    "name": "Artist",
                    "picture_big": "https://e-cdns-images.dzcdn.net/images/artist/artist-image/500x500.jpg",
                },
                "album": {"title": "Album Without Cover"},
            }
        ]

    monkeypatch.setattr(
        search_router.deezer_service, "search_tracks", fake_search_tracks
    )

    results = await search_router._search_deezer_tracks("query", limit=3)

    assert len(results) == 1
    result = results[0]
    assert (
        result.image_url
        == "https://e-cdns-images.dzcdn.net/images/artist/artist-image/500x500.jpg"
    )
    assert result.external_ids == {"deezer_id": "42", "deezer_artist_id": "7"}


@pytest.mark.asyncio
async def test_search_endpoint_returns_local_results_without_local_task_errors(
    monkeypatch, caplog
):
    class FakeDbSession:
        def __init__(self):
            self.in_use = False

        async def local_query(self, item_type: str):
            if self.in_use:
                raise RuntimeError("concurrent local query on same session")
            self.in_use = True
            try:
                await asyncio.sleep(0)
                return [
                    search_router.SearchResultItem(
                        id=f"local-{item_type}",
                        type=item_type,
                        name=f"Local {item_type}",
                        source="local",
                        in_library=True,
                    )
                ]
            finally:
                self.in_use = False

    fake_db = FakeDbSession()

    async def fake_local_artists(db, _query, _limit):
        assert db is fake_db
        return await db.local_query("artist")

    async def fake_local_albums(db, _query, _limit, artist_filter=None):
        assert artist_filter is None
        assert db is fake_db
        return await db.local_query("album")

    async def fake_local_tracks(db, _query, _limit):
        assert db is fake_db
        return await db.local_query("track")

    async def return_empty(*_args, **_kwargs):
        return []

    monkeypatch.setattr(search_router, "_search_local_artists", fake_local_artists)
    monkeypatch.setattr(search_router, "_search_local_albums", fake_local_albums)
    monkeypatch.setattr(search_router, "_search_local_tracks", fake_local_tracks)

    monkeypatch.setattr(search_router, "_search_deezer_artists", return_empty)
    monkeypatch.setattr(search_router, "_search_deezer_albums", return_empty)
    monkeypatch.setattr(search_router, "_search_deezer_tracks", return_empty)
    monkeypatch.setattr(search_router, "_search_lastfm_artists", return_empty)
    monkeypatch.setattr(search_router, "_search_lastfm_albums", return_empty)
    monkeypatch.setattr(search_router, "_search_lastfm_tracks", return_empty)
    monkeypatch.setattr(search_router, "_search_ytmusic_artists", return_empty)
    monkeypatch.setattr(search_router, "_search_ytmusic_albums", return_empty)
    monkeypatch.setattr(search_router, "_search_ytmusic_tracks", return_empty)

    app = FastAPI()
    app.include_router(search_router.router, prefix="/api/search")

    async def override_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = override_get_db

    with caplog.at_level("ERROR"):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.get("/api/search", params={"q": "local"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["artists"][0]["source"] == "local"
    assert payload["albums"][0]["source"] == "local"
    assert payload["tracks"][0]["source"] == "local"
    assert "Search task local_" not in caplog.text


@pytest.mark.asyncio
async def test_get_preview_deezer_artist_uses_helper_image_fallbacks(monkeypatch):
    async def fake_search_artists(_name: str, limit: int = 1):
        assert limit == 1
        return [{"id": 99, "name": "Fallback Artist", "picture_small": "https://img/artist-small.jpg"}]

    async def fake_get_artist_albums(artist_id: int, limit: int = 8):
        assert artist_id == 99
        assert limit == 8
        return [
            {
                "title": "Medium Cover Album",
                "cover_medium": "https://img/album-medium.jpg",
                "release_date": "2022-05-01",
            },
            {
                "title": "Small Cover Album",
                "cover_small": "https://img/album-small.jpg",
                "release_date": "2021-03-01",
            },
        ]

    async def fake_get_artist_top_tracks(artist_id: int, limit: int = 12):
        assert artist_id == 99
        assert limit == 12
        return [{"title": "Top Track", "duration": 123, "track_position": 1}]

    monkeypatch.setattr(search_router.deezer_service, "search_artists", fake_search_artists)
    monkeypatch.setattr(
        search_router.deezer_service, "get_artist_albums", fake_get_artist_albums
    )
    monkeypatch.setattr(
        search_router.deezer_service,
        "get_artist_top_tracks",
        fake_get_artist_top_tracks,
    )

    response = await search_router.get_preview(
        type="artist", name="Fallback Artist", source="deezer", db=None
    )

    assert response.image_url == "https://img/artist-small.jpg"
    assert response.top_albums[0]["image_url"] == "https://img/album-medium.jpg"
    assert response.top_albums[1]["image_url"] == "https://img/album-small.jpg"
    assert response.top_albums[0]["release_year"] == 2022


@pytest.mark.asyncio
async def test_get_preview_deezer_artist_album_image_uses_md5_fallback(monkeypatch):
    async def fake_search_artists(_name: str, limit: int = 1):
        return [{"id": 5, "name": "MD5 Artist", "md5_image": "artistmd5"}]

    async def fake_get_artist_albums(_artist_id: int, limit: int = 8):
        assert limit == 8
        return [{"title": "MD5 Album", "md5_image": "albummd5"}]

    async def fake_get_artist_top_tracks(_artist_id: int, limit: int = 12):
        assert limit == 12
        return []

    monkeypatch.setattr(search_router.deezer_service, "search_artists", fake_search_artists)
    monkeypatch.setattr(
        search_router.deezer_service, "get_artist_albums", fake_get_artist_albums
    )
    monkeypatch.setattr(
        search_router.deezer_service,
        "get_artist_top_tracks",
        fake_get_artist_top_tracks,
    )

    response = await search_router.get_preview(
        type="artist", name="MD5 Artist", source="deezer", db=None
    )

    assert (
        response.image_url
        == "https://e-cdns-images.dzcdn.net/images/artist/artistmd5/1000x1000-000000-80-0-0.jpg"
    )
    assert (
        response.top_albums[0]["image_url"]
        == "https://e-cdns-images.dzcdn.net/images/album/albummd5/1000x1000-000000-80-0-0.jpg"
    )
