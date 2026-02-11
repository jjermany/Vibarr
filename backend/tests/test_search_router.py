import pytest

from app.routers import search as search_router


def test_deezer_image_from_payload_uses_md5_fallback():
    payload = {"md5_image": "abc123"}

    image_url = search_router._deezer_image_from_payload(payload, "album")

    assert (
        image_url
        == "https://e-cdns-images.dzcdn.net/images/album/abc123/1000x1000-000000-80-0-0.jpg"
    )


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
