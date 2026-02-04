"""External service integrations."""

from app.services.spotify import SpotifyService
from app.services.lastfm import LastFMService
from app.services.musicbrainz import MusicBrainzService
from app.services.plex import PlexService
from app.services.prowlarr import ProwlarrService
from app.services.audiodb import AudioDBService

__all__ = [
    "SpotifyService",
    "LastFMService",
    "MusicBrainzService",
    "PlexService",
    "ProwlarrService",
    "AudioDBService",
]
