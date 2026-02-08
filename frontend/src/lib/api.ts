import axios from 'axios'

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// Types

export interface Artist {
  id: number
  name: string
  sort_name?: string
  musicbrainz_id?: string
  spotify_id?: string
  biography?: string
  country?: string
  image_url?: string
  thumb_url?: string
  genres?: string[]
  tags?: string[]
  avg_danceability?: number
  avg_energy?: number
  avg_valence?: number
  avg_tempo?: number
  spotify_popularity?: number
  lastfm_listeners?: number
  lastfm_playcount?: number
  in_library: boolean
  created_at: string
  updated_at: string
}

export interface Album {
  id: number
  title: string
  artist_id: number
  album_type?: string
  release_type?: string
  spotify_id?: string
  release_date?: string
  release_year?: number
  label?: string
  total_tracks?: number
  cover_url?: string
  thumb_url?: string
  genres?: string[]
  avg_danceability?: number
  avg_energy?: number
  avg_valence?: number
  spotify_popularity?: number
  in_library: boolean
  format?: string
  bitrate?: number
  artist?: Artist
  created_at: string
}

export interface Track {
  id: number
  title: string
  album_id: number
  track_number?: number
  disc_number?: number
  spotify_id?: string
  duration_ms?: number
  danceability?: number
  energy?: number
  valence?: number
  tempo?: number
  acousticness?: number
  instrumentalness?: number
  in_library: boolean
  album?: Album
}

export interface SearchResult {
  id: string
  type: string
  name: string
  artist_name?: string
  album_name?: string
  image_url?: string
  year?: number
  source: string
  in_library: boolean
  external_ids: Record<string, string>
}

export interface SearchResponse {
  query: string
  total: number
  artists: SearchResult[]
  albums: SearchResult[]
  tracks: SearchResult[]
}

export interface Recommendation {
  id: number
  type: string
  artist_id?: number
  album_id?: number
  track_id?: number
  category: string
  reason?: string
  confidence_score: number
  relevance_score: number
  novelty_score: number
  artist_name?: string
  album_title?: string
  image_url?: string
}

export interface WishlistItem {
  id: number
  item_type: string
  artist_id?: number
  album_id?: number
  artist_name?: string
  album_title?: string
  status: string
  priority: string
  source: string
  confidence_score?: number
  auto_download: boolean
  created_at: string
}

export interface WishlistCreateParams {
  item_type: string
  artist_id?: number
  album_id?: number
  artist_name?: string
  album_title?: string
  musicbrainz_id?: string
  spotify_id?: string
  priority?: string
  preferred_format?: string
  auto_download?: boolean
  notes?: string
}

export interface Download {
  id: number
  album_id?: number
  wishlist_id?: number
  artist_name: string
  album_title: string
  status: string
  status_message?: string
  release_title?: string
  release_size?: number
  release_format?: string
  release_quality?: string
  seeders?: number
  leechers?: number
  progress: number
  download_speed?: number
  eta_seconds?: number
  source: string
  beets_imported: boolean
  final_path?: string
  created_at: string
  started_at?: string
  completed_at?: string
}

export interface DownloadStats {
  total: number
  pending: number
  searching: number
  downloading: number
  importing: number
  completed: number
  failed: number
  active_client_downloads: number
}

export interface ReleaseSearchResult {
  guid: string
  indexer?: string
  indexer_id?: number
  title: string
  size: number
  format?: string
  quality?: string
  seeders: number
  leechers: number
  download_url?: string
  score: number
}

export interface GrabRequest {
  guid: string
  indexer_id: number
  download_id?: number
  artist_name?: string
  album_title?: string
  release_title?: string
  release_size?: number
  release_format?: string
  release_quality?: string
  seeders?: number
  indexer_name?: string
}

export interface QualityProfile {
  id: number
  name: string
  description?: string
  is_default: boolean
  preferred_formats: string[]
  min_quality: string
  max_size_mb: number
  min_seeders: number
  prefer_well_seeded: boolean
  format_match_weight: number
  seeder_weight: number
}

export interface ServiceStatus {
  prowlarr: { configured: boolean; connected: boolean }
  qbittorrent: { configured: boolean; connected: boolean; url?: string; category?: string; version?: string }
  beets: { available: boolean; version?: string; reason?: string }
}

export interface DownloadSettings {
  auto_download_enabled: boolean
  auto_download_confidence_threshold: number
  preferred_quality: string
  max_concurrent_downloads: number
  download_path: string
  completed_download_path: string
}

export interface LibraryStats {
  total_artists: number
  total_albums: number
  total_tracks: number
  total_genres: number
  total_size_bytes?: number
}

export interface ListeningStats {
  total_plays: number
  total_time_hours: number
  unique_artists: number
  unique_albums: number
  unique_tracks: number
  avg_plays_per_day: number
  top_artists: TopArtist[]
  top_albums: TopAlbum[]
  top_genres: GenreStat[]
}

export interface TopArtist {
  id: number
  name: string
  image_url?: string
  play_count: number
  total_time_ms: number
}

export interface TopAlbum {
  id: number
  title: string
  artist_name: string
  cover_url?: string
  play_count: number
  total_time_ms: number
}

export interface GenreStat {
  genre: string
  play_count: number
  percentage: number
}

export interface TasteProfile {
  id: number
  version: number
  top_genres: string[]
  genre_weights: Record<string, number>
  preferred_decades: number[]
  decade_weights: Record<string, number>
  avg_danceability?: number
  avg_energy?: number
  avg_valence?: number
  avg_tempo?: number
  total_plays: number
  total_artists: number
  peak_listening_hours: number[]
  peak_listening_days: number[]
  novelty_preference: number
}

// Phase 5 Types

export interface AppUser {
  id: number
  username: string
  email?: string
  display_name: string
  avatar_url?: string
  bio?: string
  is_admin: boolean
  profile_public: boolean
  share_listening_activity: boolean
  share_library: boolean
  taste_cluster?: string
  taste_tags: string[]
  created_at: string
}

export interface UserProfile extends AppUser {
  follower_count: number
  following_count: number
  is_following: boolean
}

export interface FollowUser {
  id: number
  username: string
  display_name: string
  avatar_url?: string
  taste_cluster?: string
}

export interface SharedPlaylist {
  id: number
  name: string
  description?: string
  cover_url?: string
  is_public: boolean
  collaborative: boolean
  total_tracks: number
  owner?: { id: number; display_name: string }
  items?: SharedPlaylistItem[]
  created_at: string
  updated_at: string
}

export interface SharedPlaylistItem {
  id: number
  position: number
  track_id?: number
  album_id?: number
  artist_id?: number
  note?: string
  added_by_id: number
  created_at: string
}

export interface ActivityItem {
  id: number
  user?: { id: number; display_name: string; avatar_url?: string }
  activity_type: string
  message?: string
  artist_id?: number
  album_id?: number
  track_id?: number
  playlist_id?: number
  metadata?: Record<string, any>
  created_at: string
}

export interface CompatibilityResult {
  compatibility_score: number | null
  user?: { id: number; display_name: string; taste_cluster?: string }
  per_feature: Record<string, number>
  message?: string
}

export interface AutomationRule {
  id: number
  name: string
  description?: string
  is_enabled: boolean
  trigger: string
  schedule_cron?: string
  conditions: RuleCondition[]
  actions: RuleAction[]
  priority: number
  last_triggered_at?: string
  trigger_count: number
  last_error?: string
  created_at: string
  updated_at: string
}

export interface RuleCondition {
  field: string
  operator: string
  value: any
}

export interface RuleAction {
  type: string
  params: Record<string, any>
}

export interface AutomationLog {
  id: number
  rule_id: number
  trigger_type: string
  success: boolean
  actions_executed: Record<string, any>[]
  error_message?: string
  matched_items?: Record<string, any>[]
  created_at: string
}

export interface AutomationStats {
  total_rules: number
  active_rules: number
  total_executions: number
  successful_executions: number
  failed_executions: number
}

// API Functions

export const searchApi = {
  search: (query: string, type?: string) =>
    api.get<SearchResponse>('/api/search', { params: { q: query, type } }),
  artists: (query: string, limit?: number) =>
    api.get('/api/search/artists', { params: { q: query, limit } }),
  albums: (query: string, artist?: string, limit?: number) =>
    api.get('/api/search/albums', { params: { q: query, artist, limit } }),
  tracks: (query: string, limit?: number) =>
    api.get('/api/search/tracks', { params: { q: query, limit } }),
}

export const discoveryApi = {
  getHome: () => api.get('/api/discovery/home'),
  getSimilar: (artistId: number, limit?: number) =>
    api.get(`/api/discovery/similar/${artistId}`, { params: { limit } }),
  getGenre: (genre: string, sort?: string) =>
    api.get(`/api/discovery/genre/${genre}`, { params: { sort } }),
  getDecade: (decade: number, genre?: string) =>
    api.get(`/api/discovery/decade/${decade}`, { params: { genre } }),
  getMood: (mood: string) => api.get(`/api/discovery/mood/${mood}`),
  getPlaylists: () => api.get('/api/discovery/playlists'),
  refresh: () => api.post('/api/discovery/refresh'),
}

export const libraryApi = {
  getStats: () => api.get<LibraryStats>('/api/library/stats'),
  getArtists: (params?: Record<string, any>) =>
    api.get('/api/library/artists', { params }),
  getAlbums: (params?: Record<string, any>) =>
    api.get('/api/library/albums', { params }),
  getRecent: (limit?: number) =>
    api.get('/api/library/recent', { params: { limit } }),
  sync: (fullSync?: boolean) =>
    api.post('/api/library/sync', null, { params: { full_sync: fullSync } }),
  getSyncStatus: () => api.get('/api/library/sync/status'),
  getGenres: () => api.get('/api/library/genres'),
  getDecades: () => api.get('/api/library/decades'),
}

export const artistsApi = {
  list: (params?: Record<string, any>) =>
    api.get('/api/artists', { params }),
  get: (id: number) => api.get<Artist>(`/api/artists/${id}`),
  getAlbums: (id: number) => api.get(`/api/artists/${id}/albums`),
  getSimilar: (id: number) => api.get(`/api/artists/${id}/similar`),
  refresh: (id: number) => api.post(`/api/artists/${id}/refresh`),
}

export const albumsApi = {
  list: (params?: Record<string, any>) =>
    api.get('/api/albums', { params }),
  get: (id: number) => api.get<Album>(`/api/albums/${id}`),
  getTracks: (id: number) => api.get(`/api/albums/${id}/tracks`),
  refresh: (id: number) => api.post(`/api/albums/${id}/refresh`),
  newReleases: () => api.get('/api/albums/new-releases'),
}

export const recommendationsApi = {
  list: (params?: { category?: string; type?: string; min_confidence?: number; limit?: number }) =>
    api.get<Recommendation[]>('/api/recommendations', { params }),
  categories: () => api.get('/api/recommendations/categories'),
  dismiss: (id: number) => api.post(`/api/recommendations/${id}/dismiss`),
  click: (id: number) => api.post(`/api/recommendations/${id}/click`),
  addToWishlist: (id: number) => api.post(`/api/recommendations/${id}/wishlist`),
  generate: (category?: string) =>
    api.post('/api/recommendations/generate', null, { params: { category } }),
  stats: () => api.get('/api/recommendations/stats'),
}

export const wishlistApi = {
  list: (params?: { status?: string; priority?: string; item_type?: string; sort?: string }) =>
    api.get<WishlistItem[]>('/api/wishlist', { params }),
  get: (id: number) => api.get<WishlistItem>(`/api/wishlist/${id}`),
  create: (data: WishlistCreateParams) => api.post<WishlistItem>('/api/wishlist', data),
  update: (id: number, data: Partial<WishlistItem>) =>
    api.patch<WishlistItem>(`/api/wishlist/${id}`, data),
  delete: (id: number) => api.delete(`/api/wishlist/${id}`),
  search: (id: number) => api.post(`/api/wishlist/${id}/search`),
  searchAll: () => api.post('/api/wishlist/search-all'),
}

export const downloadsApi = {
  list: (params?: { status?: string; source?: string; limit?: number }) =>
    api.get<Download[]>('/api/downloads', { params }),
  stats: () => api.get<DownloadStats>('/api/downloads/stats'),
  queue: () => api.get<Download[]>('/api/downloads/queue'),
  history: (limit?: number) =>
    api.get<Download[]>('/api/downloads/history', { params: { limit } }),
  get: (id: number) => api.get<Download>(`/api/downloads/${id}`),
  add: (data: { artist_name: string; album_title: string; preferred_format?: string; album_id?: number; wishlist_id?: number }) =>
    api.post<Download>('/api/downloads', data),
  cancel: (id: number) => api.delete(`/api/downloads/${id}`),
  retry: (id: number) => api.post<Download>(`/api/downloads/${id}/retry`),
  pause: (id: number) => api.post(`/api/downloads/${id}/pause`),
  resume: (id: number) => api.post(`/api/downloads/${id}/resume`),
  search: (artist: string, album: string, format?: string) =>
    api.post<ReleaseSearchResult[]>('/api/downloads/search', null, {
      params: { artist, album, format },
    }),
  grab: (data: GrabRequest) => api.post<Download>('/api/downloads/grab', data),
}

export const settingsApi = {
  getDownloadSettings: () =>
    api.get<DownloadSettings>('/api/settings/download'),
  getServiceStatus: () =>
    api.get<ServiceStatus>('/api/settings/services'),
  getQualityProfiles: () =>
    api.get<QualityProfile[]>('/api/settings/quality-profiles'),
  createQualityProfile: (data: Partial<QualityProfile>) =>
    api.post<QualityProfile>('/api/settings/quality-profiles', data),
  updateQualityProfile: (id: number, data: Partial<QualityProfile>) =>
    api.patch<QualityProfile>(`/api/settings/quality-profiles/${id}`, data),
  deleteQualityProfile: (id: number) =>
    api.delete(`/api/settings/quality-profiles/${id}`),
  getBeetsConfig: () => api.get('/api/settings/beets/config'),
  getBeetsLibrary: (query?: string) =>
    api.get('/api/settings/beets/library', { params: { query } }),
  generateBeetsConfig: () => api.post('/api/settings/beets/generate-config'),
}

export const statsApi = {
  overview: (days?: number) =>
    api.get<ListeningStats>('/api/stats/overview', { params: { days } }),
  topArtists: (days?: number, limit?: number) =>
    api.get('/api/stats/top-artists', { params: { days, limit } }),
  topAlbums: (days?: number, limit?: number) =>
    api.get('/api/stats/top-albums', { params: { days, limit } }),
  topTracks: (days?: number, limit?: number) =>
    api.get('/api/stats/top-tracks', { params: { days, limit } }),
  topGenres: (days?: number, limit?: number) =>
    api.get('/api/stats/top-genres', { params: { days, limit } }),
  listeningTime: (days?: number, groupBy?: string) =>
    api.get('/api/stats/listening-time', { params: { days, group_by: groupBy } }),
  listeningPatterns: (days?: number) =>
    api.get('/api/stats/listening-patterns', { params: { days } }),
  audioFeatures: (days?: number) =>
    api.get('/api/stats/audio-features', { params: { days } }),
  discoveryStats: (days?: number) =>
    api.get('/api/stats/discovery-stats', { params: { days } }),
  decadeBreakdown: (days?: number) =>
    api.get('/api/stats/decade-breakdown', { params: { days } }),
  streak: () => api.get('/api/stats/streak'),
  libraryGrowth: (days?: number) =>
    api.get('/api/stats/library-growth', { params: { days } }),
  comparison: (days?: number) =>
    api.get('/api/stats/comparison', { params: { days } }),
}

// Phase 5: Authentication
export const authApi = {
  register: (data: { username: string; email: string; password: string; display_name?: string }) =>
    api.post('/api/auth/register', data),
  login: (data: { username: string; password: string }) =>
    api.post('/api/auth/login', data),
  getProfile: () => api.get<AppUser>('/api/auth/me'),
  updateProfile: (data: Partial<AppUser>) => api.patch('/api/auth/me', data),
  listUsers: () => api.get<AppUser[]>('/api/auth/users'),
  getUser: (userId: number) => api.get<UserProfile>(`/api/auth/users/${userId}`),
}

// Phase 5: Social
export const socialApi = {
  follow: (userId: number) => api.post('/api/social/follow', { user_id: userId }),
  unfollow: (userId: number) => api.delete(`/api/social/follow/${userId}`),
  getFollowers: (userId: number) => api.get<FollowUser[]>(`/api/social/followers/${userId}`),
  getFollowing: (userId: number) => api.get<FollowUser[]>(`/api/social/following/${userId}`),
  getCompatibility: (userId: number) => api.get<CompatibilityResult>(`/api/social/compatibility/${userId}`),
  // Playlists
  listPlaylists: () => api.get<SharedPlaylist[]>('/api/social/playlists'),
  createPlaylist: (data: { name: string; description?: string; is_public?: boolean; collaborative?: boolean }) =>
    api.post<SharedPlaylist>('/api/social/playlists', data),
  getPlaylist: (id: number) => api.get<SharedPlaylist>(`/api/social/playlists/${id}`),
  updatePlaylist: (id: number, data: Partial<SharedPlaylist>) =>
    api.patch(`/api/social/playlists/${id}`, data),
  deletePlaylist: (id: number) => api.delete(`/api/social/playlists/${id}`),
  addPlaylistItem: (playlistId: number, data: { track_id?: number; album_id?: number; artist_id?: number; note?: string }) =>
    api.post(`/api/social/playlists/${playlistId}/items`, data),
  removePlaylistItem: (playlistId: number, itemId: number) =>
    api.delete(`/api/social/playlists/${playlistId}/items/${itemId}`),
  // Activity
  getActivity: (days?: number, limit?: number) =>
    api.get<ActivityItem[]>('/api/social/activity', { params: { days, limit } }),
  getGlobalActivity: (limit?: number) =>
    api.get<ActivityItem[]>('/api/social/activity/global', { params: { limit } }),
}

// Phase 5: Automation
export const automationApi = {
  listRules: (params?: { trigger?: string; enabled_only?: boolean }) =>
    api.get<AutomationRule[]>('/api/automation', { params }),
  createRule: (data: Partial<AutomationRule>) =>
    api.post<AutomationRule>('/api/automation', data),
  getTriggers: () => api.get('/api/automation/triggers'),
  getRule: (id: number) => api.get<AutomationRule>(`/api/automation/${id}`),
  updateRule: (id: number, data: Partial<AutomationRule>) =>
    api.patch<AutomationRule>(`/api/automation/${id}`, data),
  deleteRule: (id: number) => api.delete(`/api/automation/${id}`),
  testRule: (id: number, data: { item: Record<string, any>; item_type?: string }) =>
    api.post(`/api/automation/${id}/test`, data),
  toggleRule: (id: number) => api.post(`/api/automation/${id}/toggle`),
  getRuleLogs: (id: number, limit?: number) =>
    api.get<AutomationLog[]>(`/api/automation/${id}/logs`, { params: { limit } }),
  getStats: () => api.get<AutomationStats>('/api/automation/stats/summary'),
}

export default api
