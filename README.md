# Vibarr

Music Metadata Discovery & Recommendation Engine built for unRAID and self-hosted music libraries.

## Overview

Vibarr is a comprehensive music discovery and management system that combines multiple metadata sources with intelligent recommendation algorithms to help you discover new music and manage your collection. It integrates seamlessly with Plex for library management, Prowlarr for indexer search, qBittorrent for downloads, and beets for post-download tagging and organization.

## Features

### Metadata & Discovery
- **Multi-source metadata**: Aggregates data from Spotify, Last.fm, MusicBrainz, TheAudioDB, and Discogs
- **Audio feature analysis**: Uses Spotify's audio features (danceability, energy, valence, tempo) for intelligent recommendations
- **Similar artist discovery**: Leverages Last.fm's similar artist network
- **Comprehensive release data**: Full discography tracking with release types, labels, and catalog numbers

### Recommendation Engine
- **Discover Weekly**: Personalized weekly discovery playlists based on your taste
- **Release Radar**: New releases from artists you follow
- **Genre exploration**: Deep dives into genres based on your preferences
- **Mood-based recommendations**: Music matching energy levels and moods
- **Time machine**: Decade-based exploration

### Library Management
- **Plex integration**: Syncs with your Plex music library
- **Listening history tracking**: Analyzes play counts, skip rates, and completion rates
- **Taste profile building**: Learns your preferences over time
- **Quality tracking**: Monitors formats, bitrates, and audio quality

### Download Automation
- **Auto-download pipeline**: Automatically searches and downloads from your wishlist on a schedule
- **qBittorrent integration**: Full download client management with progress tracking, pause/resume, and concurrent download limits
- **Prowlarr integration**: Searches across all configured indexers with smart result scoring
- **Quality profiles**: Define format preferences (FLAC, 320, V0) with minimum quality thresholds and seeder requirements
- **Beets integration**: Automatically imports, tags, and organizes completed downloads into your music library
- **Download queue management**: Real-time progress monitoring, manual search & grab, retry failed downloads
- **Wishlist-driven automation**: Items marked for auto-download are searched hourly with configurable confidence thresholds

## Tech Stack

### Backend
- **Framework**: FastAPI (Python 3.12)
- **Database**: PostgreSQL
- **Cache/Queue**: Redis
- **Task Queue**: Celery with Celery Beat
- **API Integrations**: Spotipy, pylast, musicbrainzngs, plexapi
- **Download Client**: qBittorrent WebUI API
- **Post-Processing**: beets (optional)

### Frontend
- **Framework**: Next.js 14 (React 18)
- **Styling**: TailwindCSS
- **State Management**: TanStack Query + Zustand
- **UI Components**: Custom component library with Lucide icons

### Infrastructure
- **Containerization**: Docker & Docker Compose
- **Orchestration**: Designed for unRAID deployment

## Quick Start

### Prerequisites
- Docker and Docker Compose
- API keys for external services (see Configuration)
- qBittorrent with WebUI enabled (for downloads)
- beets installed (optional, for post-download organization)

### Development Setup

1. Clone the repository:
```bash
git clone https://github.com/jjermany/Vibarr.git
cd Vibarr
```

2. Create environment file:
```bash
cp .env.example .env
# Edit .env with your API keys and service URLs
```

3. Start the development environment:
```bash
docker-compose up -d
```

4. Access the application:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
# Spotify API (https://developer.spotify.com/)
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret

# Last.fm API (https://www.last.fm/api/account/create)
LASTFM_API_KEY=your_api_key
LASTFM_SHARED_SECRET=your_shared_secret

# Plex
PLEX_URL=http://your-plex-server:32400
PLEX_TOKEN=your_plex_token

# Prowlarr
PROWLARR_URL=http://your-prowlarr:9696
PROWLARR_API_KEY=your_api_key

# qBittorrent
QBITTORRENT_URL=http://your-qbittorrent:8080
QBITTORRENT_USERNAME=admin
QBITTORRENT_PASSWORD=your_password
QBITTORRENT_CATEGORY=vibarr

# Beets (optional)
BEETS_ENABLED=true
BEETS_LIBRARY_PATH=/music
BEETS_AUTO_IMPORT=true
BEETS_MOVE_FILES=true

# Auto-Download
AUTO_DOWNLOAD_ENABLED=false
AUTO_DOWNLOAD_CONFIDENCE_THRESHOLD=0.8
PREFERRED_QUALITY=flac
MAX_CONCURRENT_DOWNLOADS=3

# Optional: MusicBrainz User Agent
MUSICBRAINZ_USER_AGENT=Vibarr/1.0 (your@email.com)
```

### Getting API Keys

#### Spotify
1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Create a new application
3. Copy Client ID and Client Secret

#### Last.fm
1. Create an account at [Last.fm API](https://www.last.fm/api/account/create)
2. Register a new application
3. Copy API Key and Shared Secret

#### Plex
1. Sign in to Plex
2. Visit [Plex Auth Token](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/)
3. Follow instructions to get your token

#### Prowlarr
1. Open Prowlarr settings
2. Navigate to General → Security
3. Copy the API Key

#### qBittorrent
1. Open qBittorrent preferences
2. Go to Web UI tab
3. Enable the Web User Interface
4. Set a username and password
5. Note the port (default: 8080)

## Project Structure

```
Vibarr/
├── backend/
│   ├── app/
│   │   ├── models/          # SQLAlchemy models (Artist, Album, Track, Download, QualityProfile, etc.)
│   │   ├── routers/         # FastAPI route handlers (11 modules)
│   │   ├── services/        # External API integrations (Plex, Spotify, Last.fm, Prowlarr, qBittorrent, Beets)
│   │   ├── tasks/           # Celery background tasks (sync, metadata, recommendations, downloads)
│   │   ├── config.py        # Application configuration
│   │   ├── database.py      # Database setup
│   │   ├── main.py          # FastAPI application
│   │   └── celery_app.py    # Celery configuration
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/             # Next.js app router pages (Home, Search, Explore, Library, Wishlist, Downloads, Settings)
│   │   ├── components/      # React components
│   │   └── lib/             # Utilities and API client
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml
└── README.md
```

## API Endpoints

### Discovery
- `GET /api/discovery/home` - Personalized discovery feed
- `GET /api/discovery/similar/{artist_id}` - Similar artist recommendations
- `GET /api/discovery/genre/{genre}` - Genre exploration
- `GET /api/discovery/mood/{mood}` - Mood-based recommendations

### Search
- `GET /api/search` - Unified search across all sources
- `GET /api/search/artists` - Artist search
- `GET /api/search/albums` - Album search

### Library
- `GET /api/library/stats` - Library statistics
- `GET /api/library/artists` - Library artists
- `GET /api/library/albums` - Library albums
- `POST /api/library/sync` - Trigger Plex sync

### Wishlist
- `GET /api/wishlist` - List wishlist items
- `POST /api/wishlist` - Add to wishlist
- `POST /api/wishlist/{id}/search` - Search for item

### Downloads
- `GET /api/downloads` - List all downloads (filterable by status/source)
- `GET /api/downloads/stats` - Download queue statistics
- `GET /api/downloads/queue` - Active download queue
- `GET /api/downloads/history` - Completed/failed download history
- `POST /api/downloads` - Add to download queue (auto-searches via Prowlarr)
- `POST /api/downloads/search` - Manual search across indexers
- `POST /api/downloads/grab` - Grab a specific release and start downloading
- `GET /api/downloads/{id}` - Get download details
- `DELETE /api/downloads/{id}` - Cancel a download
- `POST /api/downloads/{id}/retry` - Retry a failed download
- `POST /api/downloads/{id}/pause` - Pause an active download
- `POST /api/downloads/{id}/resume` - Resume a paused download

### Settings
- `GET /api/settings/download` - Current download automation settings
- `GET /api/settings/services` - Status of Prowlarr, qBittorrent, and Beets connections
- `GET /api/settings/quality-profiles` - List quality profiles
- `POST /api/settings/quality-profiles` - Create a quality profile
- `PATCH /api/settings/quality-profiles/{id}` - Update a quality profile
- `DELETE /api/settings/quality-profiles/{id}` - Delete a quality profile
- `GET /api/settings/beets/config` - Beets configuration status
- `GET /api/settings/beets/library` - Browse beets library

## Scheduled Tasks

Vibarr runs several background tasks automatically:

| Task | Schedule | Description |
|------|----------|-------------|
| Plex Library Sync | Every 6 hours | Syncs library with Plex |
| Generate Recommendations | Daily at 3 AM | Creates daily recommendation playlists |
| Check New Releases | Every 6 hours | Monitors for new releases from library artists |
| Process Wishlist | Every hour | Searches Prowlarr for wanted items and auto-downloads |
| Update Taste Profile | Weekly (Sunday 4 AM) | Recalculates user preferences |
| Sync Listening History | Every 2 hours | Pulls latest listening data from Plex |
| Check Download Status | Every 5 minutes | Updates download progress from qBittorrent, triggers beets import on completion |

## Download Automation Pipeline

The download automation pipeline works end-to-end:

1. **Wishlist Search** - Every hour, Celery searches Prowlarr for wishlist items with auto-download enabled
2. **Quality Scoring** - Results are scored against your quality profile (format preference, seeders, size)
3. **Confidence Check** - Only results above the confidence threshold are auto-grabbed
4. **Concurrent Limits** - Downloads are throttled to respect your max concurrent download setting
5. **qBittorrent Grab** - Prowlarr sends the release to qBittorrent for downloading
6. **Progress Monitoring** - Every 5 minutes, download progress is synced from qBittorrent
7. **Beets Import** - When enabled, completed downloads are automatically imported, tagged, and organized into your music library

## Development

### Running Tests
```bash
# Backend tests
cd backend
pytest

# Frontend tests
cd frontend
npm test
```

### Code Style
```bash
# Backend formatting
cd backend
black .
isort .
flake8

# Frontend formatting
cd frontend
npm run lint
```

## Roadmap

### Phase 1: Foundation
- [x] Plex API integration
- [x] Basic metadata fetching
- [x] Simple artist/album search UI
- [x] Manual download trigger via Prowlarr

### Phase 2: Intelligence
- [x] Listening history analysis
- [x] Basic recommendation algorithm
- [x] New release monitoring
- [x] Wishlist management

### Phase 3: Automation (Current)
- [x] Auto-download pipeline
- [x] Beets integration
- [x] Quality/format preferences
- [x] Download queue management

### Phase 4: Polish
- [ ] Advanced recommendations
- [ ] Beautiful UI overhaul
- [ ] Stats and insights dashboard
- [ ] Mobile-responsive design

### Phase 5: Advanced
- [ ] ML-based taste profiling
- [ ] Social features
- [ ] Advanced automation rules
- [ ] Multi-user support

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Spotify API](https://developer.spotify.com/) for audio features and metadata
- [Last.fm API](https://www.last.fm/api) for similar artist data
- [MusicBrainz](https://musicbrainz.org/) for comprehensive music metadata
- [TheAudioDB](https://www.theaudiodb.com/) for additional artist/album info
- [Plex](https://www.plex.tv/) for media server integration
- [Prowlarr](https://prowlarr.com/) for indexer management
- [qBittorrent](https://www.qbittorrent.org/) for torrent download management
- [beets](https://beets.io/) for music library management and tagging
