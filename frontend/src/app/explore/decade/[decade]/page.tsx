'use client'

import { useParams } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import { Clock, ArrowLeft, Star } from 'lucide-react'
import { discoveryApi } from '@/lib/api'
import { ArtistCard } from '@/components/ui/ArtistCard'
import { AlbumCard } from '@/components/ui/AlbumCard'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { SectionHeader } from '@/components/ui/SectionHeader'

export default function DecadeExplorePage() {
  const params = useParams()
  const decade = parseInt(params.decade as string, 10)

  const { data, isLoading } = useQuery({
    queryKey: ['discovery', 'decade', decade],
    queryFn: () => discoveryApi.getDecade(decade),
    enabled: !isNaN(decade),
  })

  const result = data?.data
  const artists = result?.artists || []
  const albums = result?.albums || []
  const highlights = result?.highlights || []
  const label = result?.label || `${decade}s`

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

      {isLoading ? (
        <div className="flex items-center justify-center py-16">
          <LoadingSpinner size="lg" />
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
                  <AlbumCard key={album.id} album={album} size="lg" />
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
                description={`Albums from the ${label}`}
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
