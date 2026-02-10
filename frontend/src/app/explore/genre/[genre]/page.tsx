'use client'

import { useParams } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import { Music, ArrowLeft } from 'lucide-react'
import { discoveryApi } from '@/lib/api'
import { ArtistCard } from '@/components/ui/ArtistCard'
import { AlbumCard } from '@/components/ui/AlbumCard'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { SectionHeader } from '@/components/ui/SectionHeader'

export default function GenreExplorePage() {
  const params = useParams()
  const genre = decodeURIComponent(params.genre as string)

  const { data, isLoading } = useQuery({
    queryKey: ['discovery', 'genre', genre],
    queryFn: () => discoveryApi.getGenre(genre),
    enabled: !!genre,
  })

  const result = data?.data
  const artists = result?.artists || []
  const albums = result?.albums || []
  const relatedGenres = result?.related_genres || []

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
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-16">
          <LoadingSpinner size="lg" />
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
                  <ArtistCard key={artist.id} artist={artist} />
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
                  <AlbumCard key={album.id} album={album} />
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  )
}
