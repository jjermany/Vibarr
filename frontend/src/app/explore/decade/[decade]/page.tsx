'use client'

import { useState, useCallback } from 'react'
import { useParams } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import { Clock, ArrowLeft, Star } from 'lucide-react'
import { discoveryApi, wishlistApi } from '@/lib/api'
import type { SearchResult } from '@/lib/api'
import { ArtistCard } from '@/components/ui/ArtistCard'
import { AlbumCard } from '@/components/ui/AlbumCard'
import { PreviewModal } from '@/components/ui/PreviewModal'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { SectionHeader } from '@/components/ui/SectionHeader'
import toast from 'react-hot-toast'
import { useBackendReadiness } from '@/lib/useBackendReadiness'

export default function DecadeExplorePage() {
  const params = useParams()
  const decade = parseInt(params.decade as string, 10)
  const [previewItem, setPreviewItem] = useState<SearchResult | null>(null)
  const { apiUsable } = useBackendReadiness()

  const { data, isLoading } = useQuery({
    queryKey: ['discovery', 'decade', decade],
    queryFn: () => discoveryApi.getDecade(decade),
    enabled: !isNaN(decade) && apiUsable,
  })

  const result = data?.data
  const artists = result?.artists || []
  const albums = result?.albums || []
  const highlights = result?.highlights || []
  const label = result?.label || `${decade}s`

  const handlePreview = useCallback((item: any, type: string) => {
    const normalized: SearchResult = {
      id: String(item.id),
      type,
      name: item.name || item.title || '',
      artist_name: item.artist_name,
      image_url: item.image_url || item.cover_url,
      year: item.release_year,
      source: 'local',
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
      toast.success(`Added "${item.name}" to wishlist`)
      setPreviewItem(null)
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Failed to add to wishlist')
    }
  }, [])

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <Link
          href="/explore"
          className="inline-flex items-center gap-1 text-surface-400 hover:text-white text-sm mb-4 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Explore
        </Link>
        <h1 className="text-2xl font-bold text-white">The {label}</h1>
        <p className="text-surface-400 mt-1">
          Travel back in time to the music of the {label}
        </p>
      </div>

      {!apiUsable || isLoading ? (
        <div className="flex items-center justify-center py-16">
          <LoadingSpinner size="lg" />
          {!apiUsable && <span className="ml-3 text-sm text-surface-400">Starting up discovery services...</span>}
        </div>
      ) : artists.length === 0 && albums.length === 0 ? (
        <EmptyState
          icon={<Clock className="w-8 h-8" />}
          title="No results yet"
          description={`No music from the ${label} found. Try syncing your library.`}
        />
      ) : (
        <>
          {/* Highlights */}
          {highlights.length > 0 && (
            <section>
              <SectionHeader
                title="Highlights"
                description={`Top albums of the ${label}`}
              />
              <div className="flex gap-4 overflow-x-auto pb-4 -mx-4 px-4 sm:-mx-6 sm:px-6 scrollbar-hide">
                {highlights.map((album: any) => (
                  <AlbumCard
                    key={album.id}
                    album={album}
                    size="lg"
                    onClick={() => handlePreview(album, 'album')}
                    onAdd={() => handleAdd({
                      id: String(album.id),
                      type: 'album',
                      name: album.title || album.name || '',
                      artist_name: album.artist_name,
                      image_url: album.cover_url || album.image_url,
                      source: 'local',
                      in_library: album.in_library ?? false,
                      external_ids: {},
                    })}
                  />
                ))}
              </div>
            </section>
          )}

          {/* Artists */}
          {artists.length > 0 && (
            <section>
              <SectionHeader
                title="Artists"
                description={`Artists from the ${label}`}
              />
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
                      in_library: artist.in_library ?? false,
                      external_ids: {},
                    })}
                  />
                ))}
              </div>
            </section>
          )}

          {/* Albums */}
          {albums.length > 0 && (
            <section>
              <SectionHeader
                title="Albums"
                description={`Albums from the ${label}`}
              />
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
                      in_library: album.in_library ?? false,
                      external_ids: {},
                    })}
                  />
                ))}
              </div>
            </section>
          )}
        </>
      )}

      <PreviewModal
        item={previewItem}
        onClose={() => setPreviewItem(null)}
        onAdd={handleAdd}
      />
    </div>
  )
}
