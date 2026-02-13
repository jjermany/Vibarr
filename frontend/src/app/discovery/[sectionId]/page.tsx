'use client'

import { useState, useCallback } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Music, ArrowLeft } from 'lucide-react'
import { discoveryApi, wishlistApi } from '@/lib/api'
import type { SearchResult } from '@/lib/api'
import { ArtistCard } from '@/components/ui/ArtistCard'
import { AlbumCard } from '@/components/ui/AlbumCard'
import { PreviewModal } from '@/components/ui/PreviewModal'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { EmptyState } from '@/components/ui/EmptyState'
import toast from 'react-hot-toast'
import { useBackendReadiness } from '@/lib/useBackendReadiness'

export default function DiscoverySectionPage() {
  const params = useParams()
  const sectionId = params.sectionId as string
  const [previewItem, setPreviewItem] = useState<SearchResult | null>(null)
  const queryClient = useQueryClient()
  const { backendReady } = useBackendReadiness()

  const { data, isLoading } = useQuery({
    queryKey: ['discovery', 'home'],
    queryFn: () => discoveryApi.getHome(),
    enabled: backendReady,
  })

  const sections = data?.data?.sections || []
  const section = sections.find((s: any) => s.id === sectionId)
  const items = section?.items || []
  const title = section?.title || sectionId.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase())
  const description = section?.description || ''

  const handlePreview = useCallback((item: any, type: string) => {
    const normalized: SearchResult = {
      id: String(item.id),
      type,
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
        <h1 className="text-2xl font-bold text-white">{title}</h1>
        {description && <p className="text-surface-400 mt-1">{description}</p>}
      </div>

      {!backendReady || isLoading ? (
        <div className="flex items-center justify-center py-16">
          <LoadingSpinner size="lg" />
          {!backendReady && <span className="ml-3 text-sm text-surface-400">Starting up discovery services...</span>}
        </div>
      ) : !section ? (
        <EmptyState
          icon={<Music className="w-8 h-8" />}
          title="Section not found"
          description="This discovery section doesn't exist or hasn't been generated yet."
          action={
            <Link href="/" className="btn-primary">
              Back to Home
            </Link>
          }
        />
      ) : items.length === 0 ? (
        <EmptyState
          icon={<Music className="w-8 h-8" />}
          title="Nothing here yet"
          description="Start listening to music to get personalized recommendations in this section."
        />
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
          {items.map((item: any) =>
            section.type === 'artist_list' ? (
              <ArtistCard
                key={item.id}
                artist={item}
                onClick={() => handlePreview(item, 'artist')}
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
                onClick={() => handlePreview(item, 'album')}
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
