from unittest.mock import AsyncMock, Mock

import pytest

from app.services.prowlarr import ProwlarrService


def test_tokenization_normalizes_connectors_and_editions():
    service = ProwlarrService()

    tokens = service._tokenize_for_match("Artist & Album (Deluxe Edition) - Remastered")

    assert "and" in tokens
    assert "artist" in tokens
    assert "album" in tokens
    assert "deluxe" not in tokens
    assert "edition" not in tokens
    assert "remastered" not in tokens


def test_score_result_penalizes_low_text_overlap():
    service = ProwlarrService()

    strong_match = {
        "title": "The Weeknd - Dawn FM FLAC",
        "quality": "flac",
        "seeders": 20,
        "size": 500 * 1024 * 1024,
    }
    weak_match = {
        "title": "Random Compilation 2020 MP3",
        "quality": "flac",
        "seeders": 20,
        "size": 500 * 1024 * 1024,
    }

    strong_score = service._score_result(strong_match, artist="The Weeknd", album="Dawn FM")
    weak_score = service._score_result(weak_match, artist="The Weeknd", album="Dawn FM")

    assert strong_score > weak_score
    assert strong_match["passes_text_relevance"] is True
    assert weak_match["passes_text_relevance"] is False


def test_search_album_relevance_gate_prevents_irrelevant_first_place(monkeypatch):
    service = ProwlarrService()

    async def fake_search(_query, categories=None, indexer_ids=None, limit=100):
        return [
            {
                "title": "Loose Sampler FLAC",
                "quality": "flac",
                "seeders": 200,
                "size": 600 * 1024 * 1024,
            },
            {
                "title": "The Weeknd - Dawn FM 320",
                "quality": "320",
                "seeders": 30,
                "size": 120 * 1024 * 1024,
            },
        ]

    monkeypatch.setattr(service, "search", fake_search)

    ranked = __import__("asyncio").run(service.search_album(artist="The Weeknd", album="Dawn FM"))

    assert ranked[0]["title"] == "The Weeknd - Dawn FM 320"
    assert ranked[0]["passes_text_relevance"] is True
    assert ranked[1]["passes_text_relevance"] is False


def test_score_result_handles_nullable_numeric_fields():
    service = ProwlarrService()

    nullable_numeric_match = {
        "title": "The Weeknd - Dawn FM FLAC",
        "quality": "flac",
        "seeders": None,
        "size": None,
    }

    score = service._score_result(nullable_numeric_match, artist="The Weeknd", album="Dawn FM")

    assert isinstance(score, float)
    assert "text_relevance" in nullable_numeric_match
    assert "passes_text_relevance" in nullable_numeric_match


def test_score_result_handles_non_numeric_fields():
    service = ProwlarrService()

    non_numeric_match = {
        "title": "The Weeknd - Dawn FM FLAC",
        "quality": "flac",
        "seeders": "many",
        "size": "large",
    }

    score = service._score_result(non_numeric_match, artist="The Weeknd", album="Dawn FM")

    assert isinstance(score, float)
    assert "text_relevance" in non_numeric_match
    assert "passes_text_relevance" in non_numeric_match


@pytest.mark.asyncio
async def test_grab_posts_expected_payload_and_returns_success_with_optional_id(monkeypatch):
    service = ProwlarrService()

    response = Mock()
    response.content = b'{"id":"grab-123"}'
    response.json.return_value = {"id": "grab-123"}
    response.raise_for_status.return_value = None
    response.is_error = False

    client = AsyncMock()
    client.is_closed = False
    client.post.return_value = response

    monkeypatch.setattr(service, "_client", client)

    result = await service.grab(guid="abc-guid", indexer_id=42)

    assert result == {"success": True, "download_id": "grab-123"}
    client.post.assert_awaited_once()
    args, kwargs = client.post.await_args
    assert args == ("/api/v1/release",)
    assert kwargs["json"] == {"guid": "abc-guid", "indexerId": 42}


@pytest.mark.asyncio
async def test_grab_accepts_success_without_client_id(monkeypatch):
    service = ProwlarrService()

    response = Mock()
    response.content = b""
    response.raise_for_status.return_value = None
    response.is_error = False

    client = AsyncMock()
    client.is_closed = False
    client.post.return_value = response

    monkeypatch.setattr(service, "_client", client)

    result = await service.grab(guid="abc-guid", indexer_id=42)

    assert result == {"success": True, "download_id": None}
