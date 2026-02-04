'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Library as LibraryIcon, Grid, List, Filter, RefreshCw } from 'lucide-react'
import { libraryApi } from '@/lib/api'
import { AlbumCard } from '@/components/ui/AlbumCard'
import { ArtistCard } from '@/components/ui/ArtistCard'
import { LoadingPage } from '@/components/ui/LoadingSpinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { cn } from '@/lib/utils'

type ViewMode = 'albums' | 'artists'
type SortOption = 'recent' | 'name' | 'date' | 'artist'

export default function LibraryPage() {
  const [viewMode, setViewMode] = useState<ViewMode>('albums')
  const [sortBy, setSortBy] = useState<SortOption>('recent')
  const [viewStyle, setViewStyle] = useState<'grid' | 'list'>('grid')

  const { data: statsData } = useQuery({
    queryKey: ['library', 'stats'],
    queryFn: () => libraryApi.getStats(),
  })

  const { data: albumsData, isLoading: albumsLoading } = useQuery({
    queryKey: ['library', 'albums', sortBy],
    queryFn: () => libraryApi.getAlbums({ sort: sortBy }),
    enabled: viewMode === 'albums',
  })

  const { data: artistsData, isLoading: artistsLoading } = useQuery({
    queryKey: ['library', 'artists', sortBy],
    queryFn: () => libraryApi.getArtists({ sort: sortBy === 'date' ? 'recent' : sortBy }),
    enabled: viewMode === 'artists',
  })

  const stats = statsData?.data
  const albums = albumsData?.data?.albums || []
  const artists = artistsData?.data?.artists || []
  const isLoading = viewMode === 'albums' ? albumsLoading : artistsLoading

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Your Library</h1>
          {stats && (
            <p className="text-surface-400 mt-1">
              {stats.total_artists} artists &middot; {stats.total_albums} albums
            </p>
          )}
        </div>
        <button className="btn-secondary">
          <RefreshCw className="w-4 h-4" />
          Sync Library
        </button>
      </div>

      {/* Filters */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setViewMode('albums')}
            className={cn(
              'px-4 py-2 rounded-lg text-sm font-medium transition-colors',
              viewMode === 'albums'
                ? 'bg-primary-500/20 text-primary-400'
                : 'text-surface-400 hover:text-white hover:bg-surface-800'
            )}
          >
            Albums
          </button>
          <button
            onClick={() => setViewMode('artists')}
            className={cn(
              'px-4 py-2 rounded-lg text-sm font-medium transition-colors',
              viewMode === 'artists'
                ? 'bg-primary-500/20 text-primary-400'
                : 'text-surface-400 hover:text-white hover:bg-surface-800'
            )}
          >
            Artists
          </button>
        </div>

        <div className="flex items-center gap-2">
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as SortOption)}
            className="input w-40 text-sm"
          >
            <option value="recent">Recently Added</option>
            <option value="name">Name</option>
            <option value="date">Release Date</option>
            {viewMode === 'albums' && <option value="artist">Artist</option>}
          </select>

          <div className="flex items-center border border-surface-700 rounded-lg">
            <button
              onClick={() => setViewStyle('grid')}
              className={cn(
                'p-2 transition-colors',
                viewStyle === 'grid' ? 'text-primary-400' : 'text-surface-400'
              )}
            >
              <Grid className="w-4 h-4" />
            </button>
            <button
              onClick={() => setViewStyle('list')}
              className={cn(
                'p-2 transition-colors',
                viewStyle === 'list' ? 'text-primary-400' : 'text-surface-400'
              )}
            >
              <List className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      {isLoading ? (
        <LoadingPage message="Loading library..." />
      ) : viewMode === 'albums' ? (
        albums.length > 0 ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
            {albums.map((album: any) => (
              <AlbumCard key={album.id} album={album} />
            ))}
          </div>
        ) : (
          <EmptyState
            icon={<LibraryIcon className="w-8 h-8" />}
            title="No albums in library"
            description="Sync your Plex library to see your music collection here"
            action={
              <button className="btn-primary">Sync Library</button>
            }
          />
        )
      ) : artists.length > 0 ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
          {artists.map((artist: any) => (
            <ArtistCard key={artist.id} artist={artist} />
          ))}
        </div>
      ) : (
        <EmptyState
          icon={<LibraryIcon className="w-8 h-8" />}
          title="No artists in library"
          description="Sync your Plex library to see your music collection here"
          action={
            <button className="btn-primary">Sync Library</button>
          }
        />
      )}
    </div>
  )
}
