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
  progress: number
  source: string
  created_at: string
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
  list: () => api.get<Download[]>('/api/downloads'),
  queue: () => api.get<Download[]>('/api/downloads/queue'),
  history: () => api.get<Download[]>('/api/downloads/history'),
  get: (id: number) => api.get<Download>(`/api/downloads/${id}`),
  add: (data: any) => api.post('/api/downloads', data),
  cancel: (id: number) => api.delete(`/api/downloads/${id}`),
  retry: (id: number) => api.post(`/api/downloads/${id}/retry`),
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
}

export default api
