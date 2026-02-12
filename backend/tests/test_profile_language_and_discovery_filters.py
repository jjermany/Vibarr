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
