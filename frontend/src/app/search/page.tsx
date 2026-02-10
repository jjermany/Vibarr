'use client'

import { useState, useEffect, Suspense } from 'react'
import { useSearchParams } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import { Search as SearchIcon, Music, Disc, User, Check } from 'lucide-react'
import { searchApi } from '@/lib/api'
import { AlbumCard } from '@/components/ui/AlbumCard'
import { ArtistCard } from '@/components/ui/ArtistCard'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { cn } from '@/lib/utils'

type SearchType = 'all' | 'artists' | 'albums' | 'tracks'

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

  // Debounce search query
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(query)
    }, 300)
    return () => clearTimeout(timer)
  }, [query])

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ['search', debouncedQuery, searchType],
    queryFn: () => searchApi.search(debouncedQuery, searchType !== 'all' ? searchType : undefined),
    enabled: debouncedQuery.length > 0,
  })

  const results = data?.data || { artists: [], albums: [], tracks: [] }
  const hasResults =
    results.artists?.length > 0 ||
    results.albums?.length > 0 ||
    results.tracks?.length > 0

  return (
    <div className="space-y-6">
      {/* Search Input */}
      <div className="relative max-w-2xl">
        <SearchIcon className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-surface-400" />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search for artists, albums, or tracks..."
          className="w-full pl-12 pr-4 py-3 bg-surface-800 border border-surface-700 rounded-xl text-white placeholder-surface-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent text-lg"
          autoFocus
        />
        {isFetching && (
          <div className="absolute right-4 top-1/2 -translate-y-1/2">
            <LoadingSpinner size="sm" />
          </div>
        )}
      </div>

      {/* Type Filters */}
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

      {/* Results */}
      {!debouncedQuery ? (
        <EmptyState
          icon={<SearchIcon className="w-8 h-8" />}
          title="Search for music"
          description="Find artists, albums, and tracks across your library and external sources"
        />
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
                  {results.artists.map((artist: any) => (
                    <ArtistCard key={artist.id} artist={artist} />
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
                  {results.albums.map((album: any) => (
                    <AlbumCard key={album.id} album={album} />
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
                  {results.tracks.map((track: any, index: number) => (
                    <div
                      key={track.id}
                      className="flex items-center gap-4 p-3 hover:bg-surface-800/50 transition-colors"
                    >
                      <span className="w-6 text-center text-sm text-surface-500">
                        {index + 1}
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <p className="text-white truncate">{track.name || track.title}</p>
                          {track.in_library && (
                            <span className="flex-shrink-0 p-0.5 bg-green-500 rounded-full" title="In library">
                              <Check className="w-2.5 h-2.5 text-white" />
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-surface-400 truncate">
                          {track.artist_name}
                        </p>
                      </div>
                      <span className="text-sm text-surface-400">
                        {formatDuration(track.duration_ms)}
                      </span>
                    </div>
                  ))}
                </div>
              </section>
            )}
        </div>
      )}
    </div>
  )
}

function formatDuration(ms: number): string {
  if (!ms) return '--:--'
  const minutes = Math.floor(ms / 60000)
  const seconds = Math.floor((ms % 60000) / 1000)
  return `${minutes}:${seconds.toString().padStart(2, '0')}`
}
