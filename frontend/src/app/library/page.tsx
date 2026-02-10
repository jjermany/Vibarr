'use client'

import { useState, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Library as LibraryIcon, Grid, List, RefreshCw } from 'lucide-react'
import { libraryApi, wishlistApi } from '@/lib/api'
import type { SearchResult } from '@/lib/api'
import { AlbumCard } from '@/components/ui/AlbumCard'
import { ArtistCard } from '@/components/ui/ArtistCard'
import { PreviewModal } from '@/components/ui/PreviewModal'
import { LoadingPage } from '@/components/ui/LoadingSpinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { cn } from '@/lib/utils'
import toast from 'react-hot-toast'

type ViewMode = 'albums' | 'artists'
type SortOption = 'recent' | 'name' | 'date' | 'artist'

export default function LibraryPage() {
  const [viewMode, setViewMode] = useState<ViewMode>('albums')
  const [sortBy, setSortBy] = useState<SortOption>('recent')
  const [viewStyle, setViewStyle] = useState<'grid' | 'list'>('grid')
  const [previewItem, setPreviewItem] = useState<SearchResult | null>(null)

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

  const handlePreview = useCallback((item: any, type: string) => {
    const normalized: SearchResult = {
      id: String(item.id),
      type,
      name: item.name || item.title || '',
      artist_name: item.artist_name,
      image_url: item.image_url || item.cover_url || item.thumb_url,
      year: item.release_year,
      source: 'local',
      in_library: item.in_library ?? true,
      external_ids: {},
    }
    setPreviewItem(normalized)
  }, [])

  const handleAdd = useCallback(async (item: SearchResult) => {
    try {
      const isAlbum = item.type === 'album'
      await wishlistApi.create({
        item_type: isAlbum ? 'album' : 'artist',
        artist_name: item.artist_name || (isAlbum ? undefined : item.name),
        album_title: isAlbum ? item.name : undefined,
        priority: 'normal',
        auto_download: false,
      })
      toast.success(`Added "${item.name}" to wishlist`)
      setPreviewItem(null)
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Failed to add to wishlist')
    }
  }, [])

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
              <AlbumCard
                key={album.id}
                album={album}
                onClick={() => handlePreview(album, 'album')}
                onAdd={() => handleAdd({
                  id: String(album.id),
                  type: 'album',
                  name: album.title || album.name || '',
                  artist_name: album.artist_name,
                  image_url: album.cover_url || album.image_url,
                  source: 'local',
                  in_library: album.in_library ?? true,
                  external_ids: {},
                })}
              />
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
            <ArtistCard
              key={artist.id}
              artist={artist}
              onClick={() => handlePreview(artist, 'artist')}
              onAdd={() => handleAdd({
                id: String(artist.id),
                type: 'artist',
                name: artist.name || '',
                image_url: artist.image_url,
                source: 'local',
                in_library: artist.in_library ?? true,
                external_ids: {},
              })}
            />
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

      <PreviewModal
        item={previewItem}
        onClose={() => setPreviewItem(null)}
        onAdd={handleAdd}
      />
    </div>
  )
}
