"""MusicBrainz API integration for comprehensive metadata."""

from typing import Optional, List, Dict, Any
import logging

import musicbrainzngs

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Configure MusicBrainz
musicbrainzngs.set_useragent(
    "Vibarr",
    "0.1.0",
    "https://github.com/jjermany/Vibarr",
)


class MusicBrainzService:
    """MusicBrainz API service for comprehensive music metadata."""

    def __init__(self):
        """Initialize MusicBrainz service."""
        pass

    @property
    def is_available(self) -> bool:
        """Check if MusicBrainz service is available."""
        return True  # MusicBrainz is always available (no auth required)

    async def search_artists(
        self,
        query: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search for artists."""
        try:
            result = musicbrainzngs.search_artists(
                artist=query,
                limit=limit,
            )
            artists = result.get("artist-list", [])
            return [
                {
                    "id": artist.get("id"),
                    "name": artist.get("name"),
                    "sort_name": artist.get("sort-name"),
                    "disambiguation": artist.get("disambiguation"),
                    "country": artist.get("country"),
                    "type": artist.get("type"),
                    "score": artist.get("ext:score"),
                }
                for artist in artists
            ]
        except Exception as e:
            logger.error(f"MusicBrainz artist search failed: {e}")
            return []

    async def search_releases(
        self,
        query: str,
        artist: str = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search for releases (albums)."""
        try:
            kwargs = {"release": query, "limit": limit}
            if artist:
                kwargs["artist"] = artist

            result = musicbrainzngs.search_releases(**kwargs)
            releases = result.get("release-list", [])
            return [
                {
                    "id": release.get("id"),
                    "title": release.get("title"),
                    "artist": release.get("artist-credit-phrase"),
                    "date": release.get("date"),
                    "country": release.get("country"),
                    "status": release.get("status"),
                    "barcode": release.get("barcode"),
                    "score": release.get("ext:score"),
                }
                for release in releases
            ]
        except Exception as e:
            logger.error(f"MusicBrainz release search failed: {e}")
            return []

    async def search_release_groups(
        self,
        query: str,
        artist: str = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search for release groups (canonical albums)."""
        try:
            kwargs = {"releasegroup": query, "limit": limit}
            if artist:
                kwargs["artist"] = artist

            result = musicbrainzngs.search_release_groups(**kwargs)
            groups = result.get("release-group-list", [])
            return [
                {
                    "id": group.get("id"),
                    "title": group.get("title"),
                    "artist": group.get("artist-credit-phrase"),
                    "type": group.get("type"),
                    "primary_type": group.get("primary-type"),
                    "first_release_date": group.get("first-release-date"),
                    "score": group.get("ext:score"),
                }
                for group in groups
            ]
        except Exception as e:
            logger.error(f"MusicBrainz release group search failed: {e}")
            return []

    async def get_artist(self, mbid: str) -> Optional[Dict[str, Any]]:
        """Get artist by MusicBrainz ID."""
        try:
            result = musicbrainzngs.get_artist_by_id(
                mbid,
                includes=["tags", "ratings", "url-rels", "artist-rels"],
            )
            artist = result.get("artist", {})
            return {
                "id": artist.get("id"),
                "name": artist.get("name"),
                "sort_name": artist.get("sort-name"),
                "type": artist.get("type"),
                "country": artist.get("country"),
                "disambiguation": artist.get("disambiguation"),
                "life_span": artist.get("life-span"),
                "tags": [tag.get("name") for tag in artist.get("tag-list", [])],
                "rating": artist.get("rating", {}).get("value"),
                "urls": {
                    rel.get("type"): rel.get("target")
                    for rel in artist.get("url-relation-list", [])
                },
            }
        except Exception as e:
            logger.error(f"MusicBrainz get artist failed: {e}")
            return None

    async def get_artist_releases(
        self,
        mbid: str,
        release_type: List[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get all releases for an artist."""
        try:
            result = musicbrainzngs.browse_release_groups(
                artist=mbid,
                release_type=release_type or ["album", "ep", "single"],
                limit=limit,
            )
            groups = result.get("release-group-list", [])
            return [
                {
                    "id": group.get("id"),
                    "title": group.get("title"),
                    "type": group.get("type"),
                    "primary_type": group.get("primary-type"),
                    "first_release_date": group.get("first-release-date"),
                }
                for group in groups
            ]
        except Exception as e:
            logger.error(f"MusicBrainz get artist releases failed: {e}")
            return []

    async def get_release_group(self, mbid: str) -> Optional[Dict[str, Any]]:
        """Get release group by ID."""
        try:
            result = musicbrainzngs.get_release_group_by_id(
                mbid,
                includes=["artists", "tags", "ratings", "releases"],
            )
            group = result.get("release-group", {})
            return {
                "id": group.get("id"),
                "title": group.get("title"),
                "type": group.get("type"),
                "primary_type": group.get("primary-type"),
                "first_release_date": group.get("first-release-date"),
                "artist_credit": group.get("artist-credit-phrase"),
                "tags": [tag.get("name") for tag in group.get("tag-list", [])],
                "rating": group.get("rating", {}).get("value"),
                "releases": [
                    {
                        "id": rel.get("id"),
                        "title": rel.get("title"),
                        "date": rel.get("date"),
                        "country": rel.get("country"),
                        "status": rel.get("status"),
                    }
                    for rel in group.get("release-list", [])
                ],
            }
        except Exception as e:
            logger.error(f"MusicBrainz get release group failed: {e}")
            return None

    async def get_release(self, mbid: str) -> Optional[Dict[str, Any]]:
        """Get release (specific edition) by ID."""
        try:
            result = musicbrainzngs.get_release_by_id(
                mbid,
                includes=["artists", "recordings", "labels", "release-groups"],
            )
            release = result.get("release", {})
            return {
                "id": release.get("id"),
                "title": release.get("title"),
                "artist_credit": release.get("artist-credit-phrase"),
                "date": release.get("date"),
                "country": release.get("country"),
                "status": release.get("status"),
                "barcode": release.get("barcode"),
                "release_group": release.get("release-group", {}).get("id"),
                "label_info": [
                    {
                        "catalog_number": li.get("catalog-number"),
                        "label": li.get("label", {}).get("name"),
                    }
                    for li in release.get("label-info-list", [])
                ],
                "media": [
                    {
                        "format": medium.get("format"),
                        "position": medium.get("position"),
                        "track_count": medium.get("track-count"),
                        "tracks": [
                            {
                                "position": track.get("position"),
                                "title": track.get("recording", {}).get("title"),
                                "length": track.get("recording", {}).get("length"),
                                "recording_id": track.get("recording", {}).get("id"),
                            }
                            for track in medium.get("track-list", [])
                        ],
                    }
                    for medium in release.get("medium-list", [])
                ],
            }
        except Exception as e:
            logger.error(f"MusicBrainz get release failed: {e}")
            return None

    async def get_recording(self, mbid: str) -> Optional[Dict[str, Any]]:
        """Get recording (track) by ID."""
        try:
            result = musicbrainzngs.get_recording_by_id(
                mbid,
                includes=["artists", "tags", "isrcs", "releases"],
            )
            recording = result.get("recording", {})
            return {
                "id": recording.get("id"),
                "title": recording.get("title"),
                "length": recording.get("length"),
                "artist_credit": recording.get("artist-credit-phrase"),
                "tags": [tag.get("name") for tag in recording.get("tag-list", [])],
                "isrcs": recording.get("isrc-list", []),
            }
        except Exception as e:
            logger.error(f"MusicBrainz get recording failed: {e}")
            return None


# Singleton instance
musicbrainz_service = MusicBrainzService()
