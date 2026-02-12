'use client'

import { useState, useEffect, useCallback, Suspense } from 'react'
import { useSearchParams } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import { Search as SearchIcon, Music, Disc, User, Check, Plus, AlertCircle, ListMusic, Loader2 } from 'lucide-react'
import { searchApi, wishlistApi, healthApi } from '@/lib/api'
import type { SearchResult, PlaylistResolveResult, PlaylistTrack } from '@/lib/api'
import { AlbumCard } from '@/components/ui/AlbumCard'
import { ArtistCard } from '@/components/ui/ArtistCard'
import { PreviewModal } from '@/components/ui/PreviewModal'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { cn } from '@/lib/utils'
import toast from 'react-hot-toast'

type SearchType = 'all' | 'artists' | 'albums' | 'tracks'

const SEARCH_TYPE_TO_API: Record<SearchType, string | undefined> = {
  all: undefined,
  artists: 'artist',
  albums: 'album',
  tracks: 'track',
}

const PLAYLIST_URL_PATTERN = /(?:deezer\.com\/(?:\w+\/)?playlist\/\d+|(?:music\.)?youtube\.com\/playlist\?list=[\w-]+)/i

function isPlaylistUrl(q: string): boolean {
  return PLAYLIST_URL_PATTERN.test(q.trim())
}

function formatDuration(ms: number | undefined | null): string {
  if (!ms) return ''
  const totalSeconds = Math.floor(ms / 1000)
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${minutes}:${seconds.toString().padStart(2, '0')}`
}

export default function SearchPage() {
  return (
    <Suspense fallback={<div className="flex items-center justify-center py-16"><LoadingSpinner size="lg" /></div>}>
      <SearchPageContent />
    </Suspense>
  )
}

function SearchPageContent() {
  const searchParams = useSearchParams()
  const initialQuery = searchParams.get('q') || ''
  const [query, setQuery] = useState(initialQuery)
  const [searchType, setSearchType] = useState<SearchType>('all')
  const [debouncedQuery, setDebouncedQuery] = useState(initialQuery)
  const [previewItem, setPreviewItem] = useState<SearchResult | null>(null)

  // Playlist URL resolution state
  const [playlistResult, setPlaylistResult] = useState<PlaylistResolveResult | null>(null)
  const [isResolvingPlaylist, setIsResolvingPlaylist] = useState(false)
  const [isAddingPlaylist, setIsAddingPlaylist] = useState(false)

  const urlIsPlaylist = isPlaylistUrl(query)

  // Debounce search query -- skip regular search when a playlist URL is detected
  useEffect(() => {
    const timer = setTimeout(() => {
      if (urlIsPlaylist) {
        setDebouncedQuery('')
      } else {
        setDebouncedQuery(query)
        setPlaylistResult(null)
      }
    }, 300)
    return () => clearTimeout(timer)
  }, [query, urlIsPlaylist])

  const { data: readinessData, isLoading: readinessLoading } = useQuery({
    queryKey: ['backend-readiness'],
    queryFn: () => healthApi.readiness(),
    retry: false,
    refetchInterval: (query) => (query.state.data?.data?.status === 'ready' ? false : 3000),
  })

  const backendReady = readinessData?.data?.status === 'ready'

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ['search', debouncedQuery, searchType],
    queryFn: () => searchApi.search(debouncedQuery, SEARCH_TYPE_TO_API[searchType]),
    enabled: debouncedQuery.length > 0 && backendReady,
  })

  const results = data?.data || { artists: [], albums: [], tracks: [] }
  const hasResults =
    results.artists?.length > 0 ||
    results.albums?.length > 0 ||
    results.tracks?.length > 0

  const handlePreview = useCallback((item: SearchResult) => {
    setPreviewItem(item)
  }, [])

  const handleAdd = useCallback(async (item: SearchResult) => {
    try {
      const isAlbum = item.type === 'album'
      const isTrack = item.type === 'track'
      await wishlistApi.create({
        item_type: isAlbum ? 'album' : isTrack ? 'track' : 'artist',
        artist_name: item.artist_name || ((isAlbum || isTrack) ? undefined : item.name),
        album_title: isAlbum ? item.name : isTrack ? `${item.name}${item.album_name ? ` · ${item.album_name}` : ''}` : undefined,
        musicbrainz_id: item.external_ids?.musicbrainz_id,
        image_url: item.image_url,
        priority: 'normal',
        auto_download: false,
        notes: isTrack ? 'Track request from discover/search' : undefined,
      })
      toast.success(`Added "${item.name}" to wishlist`)
      setPreviewItem(null)
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Failed to add to wishlist')
    }
  }, [])

  // ---- Playlist URL handlers ----

  const handleResolvePlaylist = useCallback(async () => {
    setIsResolvingPlaylist(true)
    try {
      const res = await searchApi.resolvePlaylist(query.trim())
      setPlaylistResult(res.data)
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Failed to resolve playlist URL')
    } finally {
      setIsResolvingPlaylist(false)
    }
  }, [query])

  const handleAddPlaylist = useCallback(async (playlist: PlaylistResolveResult) => {
    setIsAddingPlaylist(true)
    let added = 0
    try {
      // 1. Create the playlist-level wishlist item
      await wishlistApi.create({
        item_type: 'playlist',
        artist_name: playlist.creator || undefined,
        album_title: playlist.title,
        image_url: playlist.image_url,
        priority: 'normal',
        auto_download: false,
        notes: `Playlist URL: ${playlist.url}`,
      })
      added++

      // 2. Create individual track items
      for (const track of playlist.tracks) {
        try {
          await wishlistApi.create({
            item_type: 'track',
            artist_name: track.artist_name || undefined,
            album_title: `${track.name}${track.album_name ? ` \u00b7 ${track.album_name}` : ''}`,
            image_url: track.image_url,
            priority: 'normal',
            auto_download: false,
            notes: `From playlist: ${playlist.title}`,
          })
          added++
        } catch {
          // Skip duplicates / failures for individual tracks
        }
      }
      toast.success(`Added playlist + ${added - 1} tracks to wishlist`)
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Failed to add playlist to wishlist')
    } finally {
      setIsAddingPlaylist(false)
    }
  }, [])

  const handleAddSingleTrack = useCallback(async (track: PlaylistTrack, playlistTitle: string) => {
    try {
      await wishlistApi.create({
        item_type: 'track',
        artist_name: track.artist_name || undefined,
        album_title: `${track.name}${track.album_name ? ` \u00b7 ${track.album_name}` : ''}`,
        image_url: track.image_url,
        priority: 'normal',
        auto_download: false,
        notes: `From playlist: ${playlistTitle}`,
      })
      toast.success(`Added "${track.name}" to wishlist`)
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Failed to add track to wishlist')
    }
  }, [])

  return (
    <div className="space-y-6">
      {/* Search Input */}
      <div className="relative max-w-2xl">
        <SearchIcon className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-surface-400" />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={backendReady ? 'Search artists, albums, tracks \u2014 or paste a playlist URL...' : 'Preparing search services...'}
          className="w-full pl-12 pr-4 py-3 bg-surface-800 border border-surface-700 rounded-xl text-white placeholder-surface-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent text-lg disabled:opacity-60 disabled:cursor-not-allowed"
          autoFocus
          disabled={!backendReady}
        />
        {(isFetching || isResolvingPlaylist) && (
          <div className="absolute right-4 top-1/2 -translate-y-1/2">
            <LoadingSpinner size="sm" />
          </div>
        )}
      </div>

      {/* Playlist URL detected banner */}
      {urlIsPlaylist && backendReady && !playlistResult && (
        <div className="flex items-center gap-3 p-3 bg-surface-800 rounded-lg border border-orange-500/30 max-w-2xl">
          <ListMusic className="w-5 h-5 text-orange-400 flex-shrink-0" />
          <span className="text-sm text-surface-300">Playlist URL detected</span>
          <button
            onClick={handleResolvePlaylist}
            disabled={isResolvingPlaylist}
            className="ml-auto btn-primary text-sm flex items-center gap-2"
          >
            {isResolvingPlaylist ? <Loader2 className="w-4 h-4 animate-spin" /> : <ListMusic className="w-4 h-4" />}
            Resolve Playlist
          </button>
        </div>
      )}

      {/* Resolved playlist view */}
      {playlistResult && (
        <section className="space-y-4">
          {/* Playlist header */}
          <div className="flex items-center gap-4 p-4 bg-surface-900 rounded-xl border border-surface-800">
            {playlistResult.image_url ? (
              <img
                src={playlistResult.image_url}
                alt={playlistResult.title}
                className="w-16 h-16 rounded-lg object-cover flex-shrink-0"
              />
            ) : (
              <div className="w-16 h-16 rounded-lg bg-surface-700 flex items-center justify-center flex-shrink-0">
                <ListMusic className="w-8 h-8 text-surface-500" />
              </div>
            )}
            <div className="min-w-0 flex-1">
              <h2 className="text-lg font-semibold text-white truncate">{playlistResult.title}</h2>
              <p className="text-sm text-surface-400">
                {playlistResult.creator && <span>By {playlistResult.creator} &middot; </span>}
                {playlistResult.track_count} tracks &middot;{' '}
                <span className="capitalize">{playlistResult.source}</span>
              </p>
              {playlistResult.description && (
                <p className="text-xs text-surface-500 mt-1 truncate">{playlistResult.description}</p>
              )}
            </div>
            <button
              onClick={() => handleAddPlaylist(playlistResult)}
              disabled={isAddingPlaylist}
              className="btn-primary flex items-center gap-2 flex-shrink-0"
            >
              {isAddingPlaylist ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
              Add to Wishlist
            </button>
          </div>

          {/* Playlist track list */}
          <div className="card divide-y divide-surface-800 max-h-[60vh] overflow-y-auto">
            {playlistResult.tracks.map((track, i) => (
              <div
                key={track.id}
                className="flex items-center gap-4 p-3 hover:bg-surface-800/50 transition-colors"
              >
                <span className="text-xs text-surface-500 w-6 text-right flex-shrink-0">{i + 1}</span>
                <div className="w-10 h-10 rounded bg-surface-700 overflow-hidden flex-shrink-0 flex items-center justify-center">
                  {track.image_url ? (
                    <img src={track.image_url} alt="" className="w-full h-full object-cover" />
                  ) : (
                    <Music className="w-5 h-5 text-surface-500" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-white truncate">{track.name}</p>
                  <p className="text-sm text-surface-400 truncate">
                    {track.artist_name}
                    {track.album_name && ` \u00b7 ${track.album_name}`}
                  </p>
                </div>
                {track.duration_ms ? (
                  <span className="text-xs text-surface-500 flex-shrink-0">
                    {formatDuration(track.duration_ms)}
                  </span>
                ) : null}
                <button
                  onClick={() => handleAddSingleTrack(track, playlistResult.title)}
                  className="flex-shrink-0 p-2 text-surface-400 hover:text-white hover:bg-surface-700 rounded-lg transition-colors"
                  title="Add to wishlist"
                >
                  <Plus className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        </section>
      )}


      {!backendReady && (
        <div className="flex items-start gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-200 max-w-2xl">
          {readinessLoading ? <LoadingSpinner size="sm" /> : <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />}
          <div>
            <p className="font-medium">Search is starting up</p>
            <p className="text-amber-200/80">
              Vibarr is still warming up services. Search will be enabled automatically when startup is complete.
            </p>
          </div>
        </div>
      )}

      {/* Type Filters -- hidden when playlist results are showing */}
      {!playlistResult && (
        <div className="flex items-center gap-2">
          {(['all', 'artists', 'albums', 'tracks'] as const).map((type) => (
            <button
              key={type}
              onClick={() => setSearchType(type)}
              className={cn(
                'px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-2',
                searchType === type
                  ? 'bg-primary-500/20 text-primary-400'
                  : 'text-surface-400 hover:text-white hover:bg-surface-800'
              )}
            >
              {type === 'artists' && <User className="w-4 h-4" />}
              {type === 'albums' && <Disc className="w-4 h-4" />}
              {type === 'tracks' && <Music className="w-4 h-4" />}
              {type.charAt(0).toUpperCase() + type.slice(1)}
            </button>
          ))}
        </div>
      )}

      {/* Regular search results -- hidden when playlist results are showing */}
      {!playlistResult && (
        <>
          {!backendReady ? (
            <EmptyState
              icon={<SearchIcon className="w-8 h-8" />}
              title="Starting search services"
              description="Please wait while backend services finish loading. The search box will enable automatically."
            />
          ) : !debouncedQuery ? (
            !urlIsPlaylist && (
              <EmptyState
                icon={<SearchIcon className="w-8 h-8" />}
                title="Search for music"
                description="Find artists, albums, and tracks across your library plus Deezer (primary) with YouTube Music fallback. You can also paste a Deezer or YouTube playlist URL."
              />
            )
          ) : isLoading ? (
            <div className="flex items-center justify-center py-16">
              <LoadingSpinner size="lg" />
            </div>
          ) : !hasResults ? (
            <EmptyState
              icon={<SearchIcon className="w-8 h-8" />}
              title="No results found"
              description={`No results for "${debouncedQuery}". Try a different search term.`}
            />
          ) : (
            <div className="space-y-8">
              {/* Artists */}
              {(searchType === 'all' || searchType === 'artists') &&
                results.artists?.length > 0 && (
                  <section>
                    <h2 className="text-lg font-semibold text-white mb-4">Artists</h2>
                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
                      {results.artists.map((artist: SearchResult) => (
                        <ArtistCard
                          key={artist.id}
                          artist={artist}
                          onClick={() => handlePreview(artist)}
                          onAdd={() => handleAdd(artist)}
                        />
                      ))}
                    </div>
                  </section>
                )}

              {/* Albums */}
              {(searchType === 'all' || searchType === 'albums') &&
                results.albums?.length > 0 && (
                  <section>
                    <h2 className="text-lg font-semibold text-white mb-4">Albums</h2>
                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
                      {results.albums.map((album: SearchResult) => (
                        <AlbumCard
                          key={album.id}
                          album={album}
                          onClick={() => handlePreview(album)}
                          onAdd={() => handleAdd(album)}
                        />
                      ))}
                    </div>
                  </section>
                )}

              {/* Tracks */}
              {(searchType === 'all' || searchType === 'tracks') &&
                results.tracks?.length > 0 && (
                  <section>
                    <h2 className="text-lg font-semibold text-white mb-4">Tracks</h2>
                    <div className="card divide-y divide-surface-800">
                      {results.tracks.map((track: SearchResult, index: number) => (
                        <div
                          key={track.id}
                          className="flex items-center gap-4 p-3 hover:bg-surface-800/50 transition-colors cursor-pointer"
                          onClick={() => handlePreview(track)}
                        >
                          {/* Track artwork */}
                          <div className="w-10 h-10 rounded bg-surface-700 overflow-hidden flex-shrink-0 flex items-center justify-center">
                            {track.image_url ? (
                              <img src={track.image_url} alt="" className="w-full h-full object-cover" />
                            ) : (
                              <Music className="w-5 h-5 text-surface-500" />
                            )}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <p className="text-white truncate">{track.name}</p>
                              {track.in_library && (
                                <span className="flex-shrink-0 p-0.5 bg-green-500 rounded-full" title="In library">
                                  <Check className="w-2.5 h-2.5 text-white" />
                                </span>
                              )}
                              {track.source !== 'local' && (
                                <span className="flex-shrink-0 text-[10px] px-1.5 py-0.5 bg-surface-700 rounded text-surface-400">
                                  {track.source === 'lastfm' ? 'Last.fm' : track.source}
                                </span>
                              )}
                            </div>
                            <p className="text-sm text-surface-400 truncate">
                              {track.artist_name}
                              {track.album_name && ` \u00b7 ${track.album_name}`}
                            </p>
                          </div>
                          {!track.in_library && (
                            <button
                              onClick={(e) => {
                                e.stopPropagation()
                                handleAdd(track)
                              }}
                              className="flex-shrink-0 p-2 text-surface-400 hover:text-white hover:bg-surface-700 rounded-lg transition-colors"
                              title="Add to wishlist"
                            >
                              <Plus className="w-4 h-4" />
                            </button>
                          )}
                        </div>
                      ))}
                    </div>
                  </section>
                )}
            </div>
          )}
        </>
      )}

      {/* Preview Modal */}
      <PreviewModal
        item={previewItem}
        onClose={() => setPreviewItem(null)}
        onAdd={handleAdd}
      />
    </div>
  )
}
