"""TheAudioDB API integration for additional metadata."""

from typing import Optional, Dict, Any
import logging

import httpx

from app.services import app_settings as cfg

logger = logging.getLogger(__name__)

AUDIODB_BASE_URL = "https://www.theaudiodb.com/api/v1/json"


class AudioDBService:
    """TheAudioDB API service for additional artist/album metadata."""

    def __init__(self):
        """Initialize AudioDB client."""
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=f"{AUDIODB_BASE_URL}/{cfg.get_setting('audiodb_api_key', '2')}",
                timeout=30.0,
            )
        return self._client

    @property
    def is_available(self) -> bool:
        """Check if AudioDB service is available."""
        return True  # Always available with free tier key

    async def search_artist(self, artist_name: str) -> Optional[Dict[str, Any]]:
        """Search for an artist by name."""
        try:
            response = await self.client.get(
                "/searchartist.php",
                params={"s": artist_name},
            )
            response.raise_for_status()
            data = response.json()

            artists = data.get("artists")
            if artists and len(artists) > 0:
                return self._normalize_artist(artists[0])
            return None
        except Exception as e:
            logger.error(f"AudioDB search artist failed: {e}")
            return None

    async def get_artist(self, audiodb_id: str) -> Optional[Dict[str, Any]]:
        """Get artist by AudioDB ID."""
        try:
            response = await self.client.get(
                "/artist.php",
                params={"i": audiodb_id},
            )
            response.raise_for_status()
            data = response.json()

            artists = data.get("artists")
            if artists and len(artists) > 0:
                return self._normalize_artist(artists[0])
            return None
        except Exception as e:
            logger.error(f"AudioDB get artist failed: {e}")
            return None

    async def get_artist_by_mbid(self, mbid: str) -> Optional[Dict[str, Any]]:
        """Get artist by MusicBrainz ID."""
        try:
            response = await self.client.get(
                "/artist-mb.php",
                params={"i": mbid},
            )
            response.raise_for_status()
            data = response.json()

            artists = data.get("artists")
            if artists and len(artists) > 0:
                return self._normalize_artist(artists[0])
            return None
        except Exception as e:
            logger.error(f"AudioDB get artist by MBID failed: {e}")
            return None

    async def get_artist_albums(self, audiodb_id: str) -> list[Dict[str, Any]]:
        """Get all albums for an artist."""
        try:
            response = await self.client.get(
                "/album.php",
                params={"i": audiodb_id},
            )
            response.raise_for_status()
            data = response.json()

            albums = data.get("album", [])
            return [self._normalize_album(album) for album in albums if album]
        except Exception as e:
            logger.error(f"AudioDB get artist albums failed: {e}")
            return []

    async def search_album(
        self,
        artist_name: str,
        album_name: str,
    ) -> Optional[Dict[str, Any]]:
        """Search for an album by artist and album name."""
        try:
            response = await self.client.get(
                "/searchalbum.php",
                params={"s": artist_name, "a": album_name},
            )
            response.raise_for_status()
            data = response.json()

            albums = data.get("album")
            if albums and len(albums) > 0:
                return self._normalize_album(albums[0])
            return None
        except Exception as e:
            logger.error(f"AudioDB search album failed: {e}")
            return None

    async def get_album(self, audiodb_id: str) -> Optional[Dict[str, Any]]:
        """Get album by AudioDB ID."""
        try:
            response = await self.client.get(
                "/album.php",
                params={"m": audiodb_id},
            )
            response.raise_for_status()
            data = response.json()

            albums = data.get("album")
            if albums and len(albums) > 0:
                return self._normalize_album(albums[0])
            return None
        except Exception as e:
            logger.error(f"AudioDB get album failed: {e}")
            return None

    async def get_album_by_mbid(self, mbid: str) -> Optional[Dict[str, Any]]:
        """Get album by MusicBrainz release group ID."""
        try:
            response = await self.client.get(
                "/album-mb.php",
                params={"i": mbid},
            )
            response.raise_for_status()
            data = response.json()

            albums = data.get("album")
            if albums and len(albums) > 0:
                return self._normalize_album(albums[0])
            return None
        except Exception as e:
            logger.error(f"AudioDB get album by MBID failed: {e}")
            return None

    async def get_album_tracks(self, audiodb_id: str) -> list[Dict[str, Any]]:
        """Get tracks for an album."""
        try:
            response = await self.client.get(
                "/track.php",
                params={"m": audiodb_id},
            )
            response.raise_for_status()
            data = response.json()

            tracks = data.get("track", [])
            return [self._normalize_track(track) for track in tracks if track]
        except Exception as e:
            logger.error(f"AudioDB get album tracks failed: {e}")
            return []

    def _normalize_artist(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize artist data from AudioDB."""
        return {
            "audiodb_id": data.get("idArtist"),
            "name": data.get("strArtist"),
            "musicbrainz_id": data.get("strMusicBrainzID"),
            "country": data.get("strCountry"),
            "formed_year": int(data["intFormedYear"]) if data.get("intFormedYear") else None,
            "disbanded_year": int(data["intDiedYear"]) if data.get("intDiedYear") else None,
            "genre": data.get("strGenre"),
            "style": data.get("strStyle"),
            "mood": data.get("strMood"),
            "biography": data.get("strBiographyEN"),
            "website": data.get("strWebsite"),
            "facebook": data.get("strFacebook"),
            "twitter": data.get("strTwitter"),
            "images": {
                "thumb": data.get("strArtistThumb"),
                "logo": data.get("strArtistLogo"),
                "fanart": data.get("strArtistFanart"),
                "fanart2": data.get("strArtistFanart2"),
                "fanart3": data.get("strArtistFanart3"),
                "banner": data.get("strArtistBanner"),
                "clearart": data.get("strArtistClearart"),
            },
        }

    def _normalize_album(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize album data from AudioDB."""
        return {
            "audiodb_id": data.get("idAlbum"),
            "title": data.get("strAlbum"),
            "artist_name": data.get("strArtist"),
            "artist_id": data.get("idArtist"),
            "musicbrainz_id": data.get("strMusicBrainzID"),
            "release_year": int(data["intYearReleased"]) if data.get("intYearReleased") else None,
            "genre": data.get("strGenre"),
            "style": data.get("strStyle"),
            "mood": data.get("strMood"),
            "label": data.get("strLabel"),
            "description": data.get("strDescriptionEN"),
            "review": data.get("strReview"),
            "score": float(data["intScore"]) if data.get("intScore") else None,
            "score_votes": int(data["intScoreVotes"]) if data.get("intScoreVotes") else None,
            "images": {
                "thumb": data.get("strAlbumThumb"),
                "thumb_back": data.get("strAlbumThumbBack"),
                "cd_art": data.get("strAlbumCDart"),
                "spine": data.get("strAlbumSpine"),
            },
        }

    def _normalize_track(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize track data from AudioDB."""
        return {
            "audiodb_id": data.get("idTrack"),
            "title": data.get("strTrack"),
            "artist_name": data.get("strArtist"),
            "album_name": data.get("strAlbum"),
            "album_id": data.get("idAlbum"),
            "track_number": int(data["intTrackNumber"]) if data.get("intTrackNumber") else None,
            "duration_ms": int(data["intDuration"]) if data.get("intDuration") else None,
            "musicbrainz_id": data.get("strMusicBrainzID"),
            "genre": data.get("strGenre"),
            "mood": data.get("strMood"),
            "description": data.get("strDescriptionEN"),
        }


# Singleton instance
audiodb_service = AudioDBService()
