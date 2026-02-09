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

### Advanced Recommendation Engine
- **Collaborative filtering**: Artist affinity matrix built from listening history with time-decay weighting
- **Multi-signal scoring**: Combines genre affinity, audio feature similarity, source artist affinity, novelty preference, and user feedback into a unified confidence score
- **Diversity boosting**: Limits per-artist and per-category recommendations to ensure varied discovery
- **Feedback loop**: Click, dismiss, and wishlist actions feed back into future recommendation scoring
- **Discover Weekly**: Personalized weekly discovery playlists based on your taste
- **Release Radar**: New releases from artists you follow
- **Genre exploration**: Deep dives into genres based on your preferences
- **Mood-based recommendations**: Music matching energy levels and moods (energetic, chill, focus)
- **Deep cuts**: Lesser-known albums from artists already in your library
- **History-based**: Recommendations driven by your most recent listening patterns

### Stats & Insights Dashboard
- **Listening overview**: Total plays, listening hours, unique artists/albums/tracks with period-over-period comparison
- **Listening streak**: Current and longest streak tracking
- **Listening activity chart**: Plays over time with area chart visualization
- **Audio profile radar**: Radar chart showing your average danceability, energy, valence, acousticness, instrumentalness, and liveness
- **Top artists & tracks**: Ranked lists with play counts and skip rates
- **Genre distribution**: Pie chart breakdown of your top genres by listening weight
- **Listening patterns**: Hourly and day-of-week bar charts showing when you listen most
- **Decade breakdown**: Bar chart of plays by release decade
- **Library growth**: Line chart tracking cumulative library size over time
- **Discovery stats**: New artists/albums discovered, recommendation click rate, discovery rate percentage

### Library Management
- **Plex integration**: Syncs with your Plex music library
- **Listening history tracking**: Analyzes play counts, skip rates, and completion rates
- **Taste profile building**: Learns your preferences over time with exponential time-decay weighting
- **Quality tracking**: Monitors formats, bitrates, and audio quality

### Download Automation
- **Auto-download pipeline**: Automatically searches and downloads from your wishlist on a schedule
- **qBittorrent integration**: Full download client management with progress tracking, pause/resume, and concurrent download limits
- **Prowlarr integration**: Searches across all configured indexers with smart result scoring
- **Quality profiles**: Define format preferences (FLAC, 320, V0) with minimum quality thresholds and seeder requirements
- **Beets integration**: Automatically imports, tags, and organizes completed downloads into your music library
- **Download queue management**: Real-time progress monitoring, manual search & grab, retry failed downloads
- **Wishlist-driven automation**: Items marked for auto-download are searched hourly with configurable confidence thresholds

### ML-Based Taste Profiling
- **Taste embeddings**: Weighted audio feature vectors computed from listening history with time-decay
- **Taste clusters**: Automatic classification into profiles (Energetic Explorer, Chill Curator, Eclectic Audiophile, Rhythm Devotee, Melancholy Romantic, Instrumental Voyager, Indie Tastemaker, High Fidelity Purist)
- **Taste evolution tracking**: Monthly snapshots track how your taste changes over time with drift rate and feature change analysis
- **Taste tags**: Auto-generated descriptive tags (e.g., "High Energy", "Dance Floor Ready", "Genre Explorer", "90s Nostalgic")
- **Predictive scoring**: ML-powered item scoring combining audio similarity (40%), genre matching (35%), novelty adjustment (15%), and data quality (10%)
- **User compatibility**: Compute taste compatibility scores between users with per-feature similarity breakdown

### Multi-User Support
- **JWT authentication**: Secure user registration and login with bcrypt password hashing
- **Household deployment**: Support for up to 10 users (configurable) with per-user data isolation
- **User profiles**: Display names, avatars, bios, and privacy controls
- **Admin system**: First registered user becomes admin automatically
- **Privacy controls**: Per-user settings for public profile visibility, listening activity sharing, and library sharing

### Social Features
- **Follow system**: Follow other household members to see their activity
- **Shared playlists**: Create and manage collaborative playlists with other users
- **Activity feed**: See what followed users are listening to, adding, and discovering
- **Global activity**: Public activity stream showing all user interactions
- **Taste compatibility**: View compatibility scores between users based on ML taste embeddings

### Advanced Automation Rules
- **Rule engine**: Define custom automation rules with conditions and actions
- **Triggers**: Rules fire on new releases, library syncs, recommendations, listening milestones, new artist discoveries, or schedules
- **Conditions**: Filter by genre, artist, album type, release year, audio features, confidence scores, format, quality, and more
- **Operators**: Equals, contains, greater/less than, in list, regex matching
- **Actions**: Auto-add to wishlist, start downloads, add to playlists, send notifications, tag items, set quality profiles
- **Rule testing**: Test rules against sample items before enabling
- **Execution logging**: Track rule triggers, successes, and failures

### Mobile-Responsive UI
- **Collapsible sidebar**: Full-width sidebar on desktop, slide-out drawer with overlay on mobile
- **Responsive layouts**: All pages adapt from mobile to desktop with appropriate grid and spacing changes
- **Touch-friendly**: Larger tap targets and swipe-friendly horizontal scroll sections on mobile

## Tech Stack

### Backend
- **Framework**: FastAPI (Python 3.12)
- **Database**: PostgreSQL
- **Cache/Queue**: Redis
- **Task Queue**: Celery with Celery Beat
- **Authentication**: JWT (python-jose) + bcrypt password hashing
- **API Integrations**: Spotipy, pylast, musicbrainzngs, plexapi
- **Download Client**: qBittorrent WebUI API
- **Post-Processing**: beets (optional)

### Frontend
- **Framework**: Next.js 14 (React 18)
- **Styling**: TailwindCSS
- **State Management**: TanStack Query + Zustand
- **Charts**: Recharts (area, bar, pie, radar, line charts)
- **UI Components**: Custom component library with Lucide icons
- **Animations**: Framer Motion + CSS transitions

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

### Unraid Installation

1. Download the Unraid template to your templates directory:
```bash
# From your Unraid terminal
wget -O /boot/config/plugins/dockerMan/templates-user/vibarr.xml \
  https://raw.githubusercontent.com/jjermany/Vibarr/main/unraid-template/vibarr.xml
```

2. In the Unraid web UI, go to **Docker** > **Add Container** > **Template** and select **Vibarr** from the dropdown.

3. Configure the required paths:
   - **Config**: `/mnt/user/appdata/vibarr` (default)
   - **Downloads**: Path to your download staging directory
   - **Music Library**: Path to your music library (same path used in Plex/beets)

4. Click **Apply** to create the container.

5. Access Vibarr at `http://your-unraid-ip:3000` and configure your services (Plex, Prowlarr, qBittorrent, etc.) via the Settings page.

> **Note**: The Vibarr container is a single all-in-one image that includes PostgreSQL, Redis, and the application. No external database setup is required.

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

# Multi-User
REGISTRATION_ENABLED=true
MAX_USERS=10

# ML Taste Profiling
ML_PROFILING_ENABLED=true
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
│   │   ├── models/          # SQLAlchemy models (Artist, Album, Track, User, Download, AutomationRule, etc.)
│   │   ├── routers/         # FastAPI route handlers (14 modules)
│   │   ├── services/        # External APIs, auth, ML profiler, automation engine
│   │   ├── tasks/           # Celery background tasks (sync, metadata, recommendations, downloads, ML profiling)
│   │   ├── config.py        # Application configuration
│   │   ├── database.py      # Database setup
│   │   ├── main.py          # FastAPI application
│   │   └── celery_app.py    # Celery configuration
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/             # Next.js app router pages (Home, Search, Explore, Library, Wishlist, Downloads, Stats, Settings, Profile, Social, Automation)
│   │   ├── components/      # React components (discovery, layout, ui)
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

### Statistics & Insights
- `GET /api/stats/overview` - Listening statistics overview (plays, time, unique counts, top artists/albums/genres)
- `GET /api/stats/top-artists` - Top artists by play count
- `GET /api/stats/top-albums` - Top albums by play count
- `GET /api/stats/top-tracks` - Top tracks by play count with skip rates
- `GET /api/stats/top-genres` - Top genres weighted by play count
- `GET /api/stats/listening-time` - Listening time grouped by hour/day/week/month
- `GET /api/stats/listening-patterns` - Hourly and daily listening distribution with peak detection
- `GET /api/stats/audio-features` - Average audio feature preferences from listening history
- `GET /api/stats/discovery-stats` - New artists/albums discovered, recommendation engagement
- `GET /api/stats/decade-breakdown` - Listening breakdown by release decade
- `GET /api/stats/streak` - Current and longest listening streaks
- `GET /api/stats/library-growth` - Library growth over time (cumulative album count)
- `GET /api/stats/comparison` - Period-over-period comparison (plays, time, artists)

### Settings
- `GET /api/settings/download` - Current download automation settings
- `GET /api/settings/services` - Status of Prowlarr, qBittorrent, and Beets connections
- `GET /api/settings/quality-profiles` - List quality profiles
- `POST /api/settings/quality-profiles` - Create a quality profile
- `PATCH /api/settings/quality-profiles/{id}` - Update a quality profile
- `DELETE /api/settings/quality-profiles/{id}` - Delete a quality profile
- `GET /api/settings/beets/config` - Beets configuration status
- `GET /api/settings/beets/library` - Browse beets library

### Authentication
- `POST /api/auth/register` - Register a new user (first user becomes admin)
- `POST /api/auth/login` - Authenticate and get JWT access token
- `GET /api/auth/me` - Get current user profile
- `PATCH /api/auth/me` - Update current user profile
- `GET /api/auth/users` - List all users with public profiles
- `GET /api/auth/users/{user_id}` - Get a user's public profile with follower counts

### Social
- `POST /api/social/follow` - Follow another user
- `DELETE /api/social/follow/{user_id}` - Unfollow a user
- `GET /api/social/followers/{user_id}` - Get a user's followers
- `GET /api/social/following/{user_id}` - Get users someone is following
- `GET /api/social/compatibility/{user_id}` - Get taste compatibility with another user
- `GET /api/social/playlists` - List shared playlists
- `POST /api/social/playlists` - Create a shared playlist
- `GET /api/social/playlists/{id}` - Get playlist details with items
- `PATCH /api/social/playlists/{id}` - Update a playlist
- `DELETE /api/social/playlists/{id}` - Delete a playlist
- `POST /api/social/playlists/{id}/items` - Add item to playlist
- `DELETE /api/social/playlists/{id}/items/{item_id}` - Remove item from playlist
- `GET /api/social/activity` - Get activity feed from followed users
- `GET /api/social/activity/global` - Get global public activity feed

### Automation Rules
- `GET /api/automation` - List automation rules
- `POST /api/automation` - Create a new automation rule
- `GET /api/automation/triggers` - List available triggers, operators, and action types
- `GET /api/automation/{id}` - Get a specific rule
- `PATCH /api/automation/{id}` - Update a rule
- `DELETE /api/automation/{id}` - Delete a rule
- `POST /api/automation/{id}/test` - Test a rule against a sample item
- `POST /api/automation/{id}/toggle` - Toggle a rule's enabled state
- `GET /api/automation/{id}/logs` - Get execution logs for a rule
- `GET /api/automation/stats/summary` - Automation execution statistics

## Scheduled Tasks

Vibarr runs several background tasks automatically:

| Task | Schedule | Description |
|------|----------|-------------|
| Plex Library Sync | Every 6 hours | Syncs library with Plex |
| Generate Recommendations | Daily at 3 AM | Creates daily recommendation playlists with advanced scoring |
| Check New Releases | Every 6 hours | Monitors for new releases from library artists |
| Process Wishlist | Every hour | Searches Prowlarr for wanted items and auto-downloads |
| Update Taste Profile | Weekly (Sunday 4 AM) | Recalculates user preferences |
| Sync Listening History | Every 2 hours | Pulls latest listening data from Plex |
| Check Download Status | Every 5 minutes | Updates download progress from qBittorrent, triggers beets import on completion |
| ML Taste Profiling | Weekly (Sunday 4:30 AM) | Computes taste embeddings, clusters, and tags for all users |
| Taste Evolution Snapshot | Monthly (1st, 5 AM) | Records taste embedding snapshot for evolution tracking |

## Download Automation Pipeline

The download automation pipeline works end-to-end:

1. **Wishlist Search** - Every hour, Celery searches Prowlarr for wishlist items with auto-download enabled
2. **Quality Scoring** - Results are scored against your quality profile (format preference, seeders, size)
3. **Confidence Check** - Only results above the confidence threshold are auto-grabbed
4. **Concurrent Limits** - Downloads are throttled to respect your max concurrent download setting
5. **qBittorrent Grab** - Prowlarr sends the release to qBittorrent for downloading
6. **Progress Monitoring** - Every 5 minutes, download progress is synced from qBittorrent
7. **Beets Import** - When enabled, completed downloads are automatically imported, tagged, and organized into your music library

## Advanced Recommendation Engine

The recommendation engine uses multiple scoring signals across two layers:

### Phase 4: Multi-Signal Scoring

1. **Time-Decay Weighting** - Recent listens are weighted exponentially higher (configurable half-life, default 14 days)
2. **Artist Affinity Matrix** - Built from listening history with completion/skip adjustments
3. **Genre Affinity** - Weighted genre preferences derived from play patterns
4. **Multi-Signal Scoring** - Each recommendation is scored across 6 dimensions:
   - Genre affinity (25%) - How well the item's genres match your preferences
   - Source artist affinity (20%) - How much you listen to the recommending artist
   - External similarity (20%) - Last.fm/Spotify similarity scores
   - Audio feature matching (15%) - Danceability, energy, valence similarity to your profile
   - Novelty adjustment (10%) - Balanced by your novelty preference
   - Feedback loop (10%) - Adjusted by your click/dismiss patterns
5. **Diversity Boosting** - Caps per-artist (max 3) and per-category (max 15) recommendations

### Phase 5: ML Taste Profiling

1. **Taste Embeddings** - 8-dimensional vectors (danceability, energy, valence, acousticness, instrumentalness, liveness, speechiness, tempo) computed from time-decayed listening history with skip penalties
2. **Cluster Classification** - Users are classified into one of 8 taste clusters using distance-based matching against predefined centroids
3. **Predictive Scoring** - ML-powered item scoring combines audio similarity (40%), genre matching (35%), novelty preference (15%), and data quality (10%)
4. **Taste Evolution** - Monthly snapshots track embedding drift over time, classifying taste trends as stable, evolving, or shifting
5. **User Compatibility** - Per-feature similarity comparison between user embeddings for social taste matching

## Automation Rules Engine

The automation rules engine enables powerful, user-defined workflows:

1. **Trigger-Condition-Action Model** - Rules fire on specific triggers (new releases, recommendations, milestones), evaluate conditions against item properties, and execute actions in sequence
2. **Flexible Conditions** - Match on genre, artist, audio features, quality, popularity, format, and more with 9 operators (equals, contains, greater/less than, regex, etc.)
3. **Composable Actions** - Chain multiple actions: add to wishlist, start downloads, add to playlists, send notifications, tag items, or skip
4. **Rule Testing** - Test rules against sample items without executing to verify condition logic
5. **Execution Logging** - Full audit trail of rule triggers, matched items, actions executed, and errors

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

### Phase 3: Automation
- [x] Auto-download pipeline
- [x] Beets integration
- [x] Quality/format preferences
- [x] Download queue management

### Phase 4: Polish
- [x] Advanced recommendation engine (collaborative filtering, time-decay, diversity boosting)
- [x] Stats & Insights dashboard with charts (area, bar, pie, radar, line)
- [x] Mobile-responsive UI with collapsible sidebar
- [x] Enhanced Discovery home with live stats
- [x] Period-over-period comparison and listening streak tracking

### Phase 5: Advanced (Current)
- [x] ML-based taste profiling (embeddings, clusters, evolution tracking, predictive scoring)
- [x] Multi-user support (JWT auth, household deployment, privacy controls)
- [x] Social features (follows, shared playlists, activity feed, taste compatibility)
- [x] Advanced automation rules (trigger-condition-action engine with logging and testing)

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
- [Recharts](https://recharts.org/) for data visualization
