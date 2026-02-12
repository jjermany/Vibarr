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
