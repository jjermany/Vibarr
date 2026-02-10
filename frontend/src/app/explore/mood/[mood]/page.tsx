'use client'

import { useParams } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import { Heart, ArrowLeft, Check } from 'lucide-react'
import { discoveryApi } from '@/lib/api'
import { AlbumCard } from '@/components/ui/AlbumCard'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { SectionHeader } from '@/components/ui/SectionHeader'

const moodMeta: Record<string, { icon: string; description: string }> = {
  energetic: { icon: '', description: 'High energy, fast tempo tracks to get you moving' },
  chill: { icon: '', description: 'Relaxed, feel-good vibes for winding down' },
  happy: { icon: '', description: 'Upbeat, danceable music to lift your spirits' },
  sad: { icon: '', description: 'Mellow, emotional tracks for reflective moments' },
  focus: { icon: '', description: 'Instrumental, steady tempo music for concentration' },
  workout: { icon: '', description: 'High energy, fast paced music to power your workout' },
}

export default function MoodExplorePage() {
  const params = useParams()
  const mood = params.mood as string

  const { data, isLoading } = useQuery({
    queryKey: ['discovery', 'mood', mood],
    queryFn: () => discoveryApi.getMood(mood),
    enabled: !!mood,
  })

  const result = data?.data
  const tracks = result?.tracks || []
  const albums = result?.albums || []
  const meta = moodMeta[mood] || { icon: '', description: `${mood} music` }

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
        <h1 className="text-2xl font-bold text-white capitalize">
          {meta.icon} {mood}
        </h1>
        <p className="text-surface-400 mt-1">{meta.description}</p>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-16">
          <LoadingSpinner size="lg" />
        </div>
      ) : tracks.length === 0 && albums.length === 0 ? (
        <EmptyState
          icon={<Heart className="w-8 h-8" />}
          title="No results yet"
          description={`No ${mood} music found. Try syncing your library to populate audio features.`}
        />
      ) : (
        <>
          {/* Albums */}
          {albums.length > 0 && (
            <section>
              <SectionHeader
                title="Albums"
                description={`Albums matching this mood`}
              />
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
                {albums.map((album: any) => (
                  <AlbumCard key={album.id} album={album} />
                ))}
              </div>
            </section>
          )}

          {/* Tracks */}
          {tracks.length > 0 && (
            <section>
              <SectionHeader
                title="Tracks"
                description={`${tracks.length} tracks matching this mood`}
              />
              <div className="card divide-y divide-surface-800">
                {tracks.map((track: any, index: number) => (
                  <div
                    key={track.id}
                    className="flex items-center gap-4 p-3 hover:bg-surface-800/50 transition-colors"
                  >
                    <span className="w-6 text-center text-sm text-surface-500">
                      {index + 1}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="text-white truncate">{track.title}</p>
                        {track.in_library && (
                          <span className="flex-shrink-0 p-0.5 bg-green-500 rounded-full" title="In library">
                            <Check className="w-2.5 h-2.5 text-white" />
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-surface-400 truncate">
                        {track.artist_name}
                        {track.album_title && ` \u00b7 ${track.album_title}`}
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
        </>
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
