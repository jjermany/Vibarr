'use client'

import { useQuery } from '@tanstack/react-query'
import { Sparkles, Radio, Compass, Clock, Music } from 'lucide-react'
import { discoveryApi, libraryApi } from '@/lib/api'
import { SectionHeader } from '@/components/ui/SectionHeader'
import { AlbumCard } from '@/components/ui/AlbumCard'
import { ArtistCard } from '@/components/ui/ArtistCard'
import { LoadingPage } from '@/components/ui/LoadingSpinner'
import { EmptyState } from '@/components/ui/EmptyState'

export function DiscoveryHome() {
  const { data: discoveryData, isLoading: discoveryLoading } = useQuery({
    queryKey: ['discovery', 'home'],
    queryFn: () => discoveryApi.getHome(),
  })

  const { data: recentData, isLoading: recentLoading } = useQuery({
    queryKey: ['library', 'recent'],
    queryFn: () => libraryApi.getRecent(10),
  })

  if (discoveryLoading || recentLoading) {
    return <LoadingPage message="Loading your personalized feed..." />
  }

  const sections = discoveryData?.data?.sections || []
  const recentAlbums = recentData?.data?.albums || []

  return (
    <div className="space-y-10">
      {/* Hero Section */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-primary-600 to-accent-600 p-8">
        <div className="relative z-10">
          <h1 className="text-3xl font-bold text-white mb-2">
            Good {getTimeOfDay()}, Music Lover
          </h1>
          <p className="text-white/80 max-w-lg">
            Discover new music tailored to your taste. We&apos;ve curated fresh
            recommendations based on your listening history.
          </p>
        </div>
        <div className="absolute right-0 top-0 w-64 h-64 bg-white/10 rounded-full blur-3xl transform translate-x-1/2 -translate-y-1/2" />
        <div className="absolute right-20 bottom-0 w-48 h-48 bg-white/10 rounded-full blur-2xl transform translate-y-1/2" />
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <QuickAction
          icon={<Sparkles className="w-5 h-5" />}
          title="Discover Weekly"
          description="Fresh picks for you"
          href="/discovery/weekly"
          color="from-purple-500 to-pink-500"
        />
        <QuickAction
          icon={<Radio className="w-5 h-5" />}
          title="Release Radar"
          description="New from your artists"
          href="/discovery/releases"
          color="from-blue-500 to-cyan-500"
        />
        <QuickAction
          icon={<Compass className="w-5 h-5" />}
          title="Explore Genres"
          description="Dive into new sounds"
          href="/explore"
          color="from-orange-500 to-red-500"
        />
        <QuickAction
          icon={<Clock className="w-5 h-5" />}
          title="Time Machine"
          description="Music by decade"
          href="/explore/decades"
          color="from-green-500 to-emerald-500"
        />
      </div>

      {/* Recently Added */}
      {recentAlbums.length > 0 && (
        <section>
          <SectionHeader
            title="Recently Added"
            description="Latest additions to your library"
            href="/library?sort=recent"
          />
          <div className="flex gap-4 overflow-x-auto pb-4 -mx-6 px-6 scrollbar-hide">
            {recentAlbums.map((album: any) => (
              <AlbumCard key={album.id} album={album} />
            ))}
          </div>
        </section>
      )}

      {/* Discovery Sections */}
      {sections.map((section: any) => (
        <section key={section.id}>
          <SectionHeader
            title={section.title}
            description={section.description}
            href={`/discovery/${section.id}`}
          />
          {section.items.length > 0 ? (
            <div className="flex gap-4 overflow-x-auto pb-4 -mx-6 px-6 scrollbar-hide">
              {section.type === 'artist_list'
                ? section.items.map((artist: any) => (
                    <ArtistCard key={artist.id} artist={artist} />
                  ))
                : section.items.map((album: any) => (
                    <AlbumCard key={album.id} album={album} />
                  ))}
            </div>
          ) : (
            <div className="card p-8">
              <EmptyState
                icon={<Music className="w-8 h-8" />}
                title="Nothing here yet"
                description="Start listening to music to get personalized recommendations"
              />
            </div>
          )}
        </section>
      ))}

      {sections.length === 0 && recentAlbums.length === 0 && (
        <EmptyState
          icon={<Sparkles className="w-8 h-8" />}
          title="Welcome to Vibarr"
          description="Connect your Plex library and start discovering new music tailored to your taste"
          action={
            <button className="btn-primary">
              Connect Plex Library
            </button>
          }
        />
      )}
    </div>
  )
}

function QuickAction({
  icon,
  title,
  description,
  href,
  color,
}: {
  icon: React.ReactNode
  title: string
  description: string
  href: string
  color: string
}) {
  return (
    <a
      href={href}
      className="card-hover p-4 flex items-center gap-4"
    >
      <div
        className={`w-12 h-12 rounded-lg bg-gradient-to-br ${color} flex items-center justify-center text-white flex-shrink-0`}
      >
        {icon}
      </div>
      <div className="min-w-0">
        <h3 className="font-semibold text-white truncate">{title}</h3>
        <p className="text-sm text-surface-400 truncate">{description}</p>
      </div>
    </a>
  )
}

function getTimeOfDay(): string {
  const hour = new Date().getHours()
  if (hour < 12) return 'morning'
  if (hour < 17) return 'afternoon'
  return 'evening'
}
