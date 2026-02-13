import pytest

from app.routers import auth, discovery


class _FakeDb:
    def __init__(self):
        self.committed = False
        self.refreshed = False

    async def commit(self):
        self.committed = True

    async def refresh(self, _user):
        self.refreshed = True


class _FakeUser:
    def __init__(self):
        self.id = 7
        self.username = "tester"
        self.email = "tester@example.com"
        self.display_name = "Tester"
        self.avatar_url = None
        self.bio = None
        self.preferred_language = None
        self.secondary_languages = []
        self.is_admin = False
        self.profile_public = True
        self.share_listening_activity = True
        self.share_library = False
        self.taste_cluster = None
        self.taste_tags = []
        self.created_at = None


@pytest.mark.asyncio
async def test_update_profile_normalizes_language_fields():
    user = _FakeUser()
    db = _FakeDb()
    request = auth.ProfileUpdateRequest(
        preferred_language=" EN ",
        secondary_languages=["ES", "en", "  pt-BR  ", ""],
    )

    await auth.update_profile(request=request, current_user=user, db=db)

    assert user.preferred_language == "en"
    assert user.secondary_languages == ["es", "pt-br"]
    assert db.committed is True
    assert db.refreshed is True


def test_discovery_language_filter_keeps_missing_metadata_and_filters_mismatch():
    user = type("U", (), {"preferred_language": "en", "secondary_languages": ["es"]})()
    langs = discovery._get_user_languages(user)

    assert langs == ["en", "es"]
    assert discovery._extract_language_metadata({"title": "No metadata"}) is None
    assert discovery._language_match("en-us", langs) is True
    assert discovery._language_match("fr", langs) is False

    summary = discovery._build_language_filter_summary(
        preferred_languages=langs,
        broaden_language=False,
        filtered_count=5,
        no_metadata_count=9,
    )

    assert summary["enabled"] is True
    assert summary["filtered_count"] == 5
    assert summary["fallback_without_metadata"] == 9


@pytest.mark.asyncio
async def test_explore_genre_uses_deezer_top_artists_and_language_filtering(monkeypatch):
    class _EmptyResult:
        class _Scalars:
            def all(self):
                return []

        def scalars(self):
            return self._Scalars()

    class _FakeDb:
        async def execute(self, _query):
            return _EmptyResult()

    async def fake_get_genres():
        return [{"id": 132, "name": "Pop"}]

    async def fake_get_genre_artists(genre_id, limit=50):
        assert genre_id == 132
        assert limit >= 40
        return [
            {"id": 1, "name": "English Artist", "nb_fan": 10},
            {"id": 2, "name": "French Artist", "nb_fan": 20},
        ]

    async def fake_get_artist_top_tracks(artist_id, limit=2):
        assert limit == 2
        if artist_id == 1:
            return [{"title": "hit", "language": "en", "artist": {"id": 1, "name": "English Artist"}}]
        return [{"title": "chanson", "language": "fr", "artist": {"id": 2, "name": "French Artist"}}]

    async def fail_search_tracks(*_args, **_kwargs):
        raise AssertionError("fallback search should not be used when Deezer genre id resolves")

    monkeypatch.setattr(discovery.deezer_service, "get_genres", fake_get_genres)
    monkeypatch.setattr(discovery.deezer_service, "get_genre_artists", fake_get_genre_artists)
    monkeypatch.setattr(discovery.deezer_service, "get_artist_top_tracks", fake_get_artist_top_tracks)
    monkeypatch.setattr(discovery.deezer_service, "search_tracks", fail_search_tracks)

    user = type("U", (), {"preferred_language": "en", "secondary_languages": []})()

    payload = await discovery.explore_genre(
        genre="pop",
        sort="popular",
        limit=10,
        broaden_language=False,
        current_user=user,
        db=_FakeDb(),
    )

    deezer_artists = [a for a in payload["artists"] if str(a["id"]).startswith("deezer:")]
    assert [artist["name"] for artist in deezer_artists] == ["English Artist"]
    assert payload["language_filter"]["filtered_count"] >= 1


@pytest.mark.asyncio
async def test_explore_genre_populates_albums_from_genre_artists_without_genre_tokens(monkeypatch):
    class _EmptyResult:
        class _Scalars:
            def all(self):
                return []

        def scalars(self):
            return self._Scalars()

    class _FakeDb:
        async def execute(self, _query):
            return _EmptyResult()

    async def fake_get_genres():
        return [{"id": 132, "name": "Pop"}]

    async def fake_get_genre_artists(genre_id, limit=50):
        assert genre_id == 132
        assert limit >= 40
        return [{"id": 99, "name": "Synth Master", "nb_fan": 100}]

    async def fake_get_artist_top_tracks(artist_id, limit=2):
        assert artist_id == 99
        assert limit == 2
        return [
            {
                "title": "Midnight Drive",
                "language": "en",
                "artist": {"id": 99, "name": "Synth Master"},
                "album": {"id": 8801, "title": "Neon Nights", "cover": "cover-url"},
            }
        ]

    async def fail_search_tracks(*_args, **_kwargs):
        raise AssertionError("fallback search should not be used when Deezer genre id resolves")

    monkeypatch.setattr(discovery.deezer_service, "get_genres", fake_get_genres)
    monkeypatch.setattr(discovery.deezer_service, "get_genre_artists", fake_get_genre_artists)
    monkeypatch.setattr(discovery.deezer_service, "get_artist_top_tracks", fake_get_artist_top_tracks)
    monkeypatch.setattr(discovery.deezer_service, "search_tracks", fail_search_tracks)

    user = type("U", (), {"preferred_language": "en", "secondary_languages": []})()

    payload = await discovery.explore_genre(
        genre="pop",
        sort="popular",
        limit=10,
        broaden_language=False,
        current_user=user,
        db=_FakeDb(),
    )

    deezer_albums = [a for a in payload["albums"] if str(a["id"]).startswith("deezer:")]
    assert deezer_albums
    assert deezer_albums[0]["title"] == "Neon Nights"
