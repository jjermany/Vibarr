'use client'

import { useState, useCallback } from 'react'
import { useParams } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import { Music, ArrowLeft } from 'lucide-react'
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

export default function GenreExplorePage() {
  const params = useParams()
  const genre = decodeURIComponent(params.genre as string)
  const [previewItem, setPreviewItem] = useState<SearchResult | null>(null)
  const [hideLowConfidence, setHideLowConfidence] = useState(true)
  const { apiUsable } = useBackendReadiness()

  const { data, isLoading } = useQuery({
    queryKey: ['discovery', 'genre', genre],
    queryFn: () => discoveryApi.getGenre(genre, undefined, true, true),
    enabled: !!genre && apiUsable,
  })

  const result = data?.data
  const confidenceThreshold = 0.75
  const artists = (result?.artists || []).filter((item: any) => !hideLowConfidence || (item.genre_match_confidence ?? 0) >= confidenceThreshold)
  const albums = (result?.albums || []).filter((item: any) => !hideLowConfidence || (item.genre_match_confidence ?? 0) >= confidenceThreshold)
  const relatedGenres = result?.related_genres || []

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
        <h1 className="text-2xl font-bold text-white capitalize">{genre}</h1>
        <p className="text-surface-400 mt-1">
          Discover {genre} artists and albums
        </p>
        <div className="mt-3 text-xs text-surface-500">
          Source labels identify local library matches vs Deezer fallback results.
        </div>
      </div>

      <label className="inline-flex items-center gap-2 text-sm text-surface-300">
        <input
          type="checkbox"
          checked={hideLowConfidence}
          onChange={(event) => setHideLowConfidence(event.target.checked)}
          className="rounded border-surface-600 bg-surface-900"
        />
        Hide low-confidence matches
      </label>


      {!apiUsable || isLoading ? (
        <div className="flex items-center justify-center py-16">
          <LoadingSpinner size="lg" />
          {!apiUsable && <span className="ml-3 text-sm text-surface-400">Starting up discovery services...</span>}
        </div>
      ) : artists.length === 0 && albums.length === 0 ? (
        <EmptyState
          icon={<Music className="w-8 h-8" />}
          title="No results yet"
          description={`No ${genre} music found. Try syncing your library or exploring other genres.`}
        />
      ) : (
        <>
          {/* Related Genres */}
          {relatedGenres.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {relatedGenres.map((g: string) => (
                <Link
                  key={g}
                  href={`/explore/genre/${encodeURIComponent(g.toLowerCase())}`}
                  className="px-3 py-1.5 rounded-full text-sm bg-surface-800 text-surface-300 hover:bg-surface-700 hover:text-white transition-colors"
                >
                  {g}
                </Link>
              ))}
            </div>
          )}

          {/* Artists */}
          {artists.length > 0 && (
            <section>
              <SectionHeader
                title="Artists"
                description={`${genre} artists`}
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
                description={`${genre} albums`}
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
