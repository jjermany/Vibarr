'use client'

import { useState, useCallback } from 'react'
import Link from 'next/link'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Radio, ArrowLeft, Music, RefreshCw } from 'lucide-react'
import { discoveryApi, wishlistApi } from '@/lib/api'
import type { SearchResult } from '@/lib/api'
import { ArtistCard } from '@/components/ui/ArtistCard'
import { AlbumCard } from '@/components/ui/AlbumCard'
import { PreviewModal } from '@/components/ui/PreviewModal'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { EmptyState } from '@/components/ui/EmptyState'
import toast from 'react-hot-toast'
import { useBackendReadiness } from '@/lib/useBackendReadiness'

export default function ReleaseRadarPage() {
  const [previewItem, setPreviewItem] = useState<SearchResult | null>(null)
  const queryClient = useQueryClient()
  const { backendReady } = useBackendReadiness()

  const { data, isLoading } = useQuery({
    queryKey: ['discovery', 'home'],
    queryFn: () => discoveryApi.getHome(),
    enabled: backendReady,
  })

  const sections = data?.data?.sections || []
  const section = sections.find((s: any) => s.id === 'release_radar')
  const items = section?.items || []

  const handlePreview = useCallback((item: any) => {
    const normalized: SearchResult = {
      id: String(item.id),
      type: item.type || 'album',
      name: item.name || item.title || '',
      artist_name: item.artist_name,
      image_url: item.image_url || item.cover_url,
      year: item.release_year,
      source: item.source || 'local',
      in_library: item.in_library ?? false,
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
      queryClient.invalidateQueries({ queryKey: ['wishlist'] })
      toast.success(`Added "${item.name}" to wishlist`)
      setPreviewItem(null)
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Failed to add to wishlist')
    }
  }, [queryClient])

  const handleRefresh = async () => {
    try {
      await discoveryApi.refresh()
      toast.success('Discovery refresh queued')
      queryClient.invalidateQueries({ queryKey: ['discovery', 'home'] })
    } catch {
      toast.error('Failed to refresh discoveries')
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <Link
          href="/"
          className="inline-flex items-center gap-1 text-surface-400 hover:text-white text-sm mb-4 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Home
        </Link>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center">
                <Radio className="w-5 h-5 text-white" />
              </div>
              Release Radar
            </h1>
            <p className="text-surface-400 mt-1">
              New releases from artists you follow
            </p>
          </div>
          <button onClick={handleRefresh} className="btn-ghost p-2" title="Refresh recommendations">
            <RefreshCw className="w-5 h-5" />
          </button>
        </div>
      </div>

      {!backendReady || isLoading ? (
        <div className="flex items-center justify-center py-16">
          <LoadingSpinner size="lg" />
          {!backendReady && <span className="ml-3 text-sm text-surface-400">Starting up discovery services...</span>}
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          icon={<Radio className="w-8 h-8" />}
          title="No new releases"
          description="New releases from artists in your library will appear here. Try syncing your library and refreshing recommendations."
          action={
            <button onClick={handleRefresh} className="btn-primary">
              <RefreshCw className="w-4 h-4" />
              Check for New Releases
            </button>
          }
        />
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
          {items.map((item: any) =>
            section?.type === 'artist_list' ? (
              <ArtistCard
                key={item.id}
                artist={item}
                onClick={() => handlePreview({ ...item, type: 'artist' })}
                onAdd={() => handleAdd({
                  id: String(item.id),
                  type: 'artist',
                  name: item.name || '',
                  image_url: item.image_url,
                  source: 'local',
                  in_library: item.in_library ?? false,
                  external_ids: {},
                })}
              />
            ) : (
              <AlbumCard
                key={item.id}
                album={item}
                onClick={() => handlePreview({ ...item, type: 'album' })}
                onAdd={() => handleAdd({
                  id: String(item.id),
                  type: 'album',
                  name: item.title || item.name || '',
                  artist_name: item.artist_name,
                  image_url: item.cover_url || item.image_url,
                  source: 'local',
                  in_library: item.in_library ?? false,
                  external_ids: {},
                })}
              />
            )
          )}
        </div>
      )}

      <PreviewModal
        item={previewItem}
        onClose={() => setPreviewItem(null)}
        onAdd={handleAdd}
      />
    </div>
  )
}
