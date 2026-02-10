'use client'

import { useState, useCallback } from 'react'
import Link from 'next/link'
import { useQuery } from '@tanstack/react-query'
import {
  Sparkles,
  Radio,
  Compass,
  Clock,
  Music,
  Flame,
  BarChart3,
  Headphones,
  TrendingUp,
} from 'lucide-react'
import { discoveryApi, libraryApi, statsApi, wishlistApi } from '@/lib/api'
import type { SearchResult } from '@/lib/api'
import { SectionHeader } from '@/components/ui/SectionHeader'
import { AlbumCard } from '@/components/ui/AlbumCard'
import { ArtistCard } from '@/components/ui/ArtistCard'
import { PreviewModal } from '@/components/ui/PreviewModal'
import { LoadingPage } from '@/components/ui/LoadingSpinner'
import { EmptyState } from '@/components/ui/EmptyState'
import toast from 'react-hot-toast'

export function DiscoveryHome() {
  const [previewItem, setPreviewItem] = useState<SearchResult | null>(null)

  const { data: discoveryData, isLoading: discoveryLoading } = useQuery({
    queryKey: ['discovery', 'home'],
    queryFn: () => discoveryApi.getHome(),
  })

  const { data: recentData, isLoading: recentLoading } = useQuery({
    queryKey: ['library', 'recent'],
    queryFn: () => libraryApi.getRecent(10),
  })

  const { data: streakData } = useQuery({
    queryKey: ['stats', 'streak'],
    queryFn: () => statsApi.streak(),
  })

  const { data: overviewData } = useQuery({
    queryKey: ['stats', 'overview', 7],
    queryFn: () => statsApi.overview(7),
  })

  const handlePreview = useCallback((item: any) => {
    // Normalize discovery item to SearchResult shape for the PreviewModal
    const normalized: SearchResult = {
      id: String(item.id),
      type: item.type || 'artist',
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
      toast.success(`Added "${item.name}" to wishlist`)
      setPreviewItem(null)
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Failed to add to wishlist')
    }
  }, [])

  if (discoveryLoading || recentLoading) {
    return <LoadingPage message="Loading your personalized feed..." />
  }

  const sections = discoveryData?.data?.sections || []
  const recentAlbums = recentData?.data?.albums || []
  const streak = streakData?.data
  const weeklyStats = overviewData?.data

  return (
    <div className="space-y-8 sm:space-y-10">
      {/* Hero Section */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-primary-600 to-accent-600 p-6 sm:p-8">
        <div className="relative z-10">
          <h1 className="text-2xl sm:text-3xl font-bold text-white mb-2">
            Good {getTimeOfDay()}, Music Lover
          </h1>
          <p className="text-white/80 max-w-lg text-sm sm:text-base">
            Discover new music tailored to your taste. We&apos;ve curated fresh
            recommendations based on your listening history.
          </p>
        </div>
        <div className="absolute right-0 top-0 w-64 h-64 bg-white/10 rounded-full blur-3xl transform translate-x-1/2 -translate-y-1/2" />
        <div className="absolute right-20 bottom-0 w-48 h-48 bg-white/10 rounded-full blur-2xl transform translate-y-1/2" />

        {/* Inline stats in hero */}
        {(streak || weeklyStats) && (
          <div className="relative z-10 mt-6 flex flex-wrap gap-4 sm:gap-6">
            {streak && streak.current_streak > 0 && (
              <div className="flex items-center gap-2 bg-white/15 backdrop-blur-sm rounded-lg px-3 py-2">
                <Flame className="w-4 h-4 text-orange-300" />
                <span className="text-white text-sm font-medium">
                  {streak.current_streak} day streak
                </span>
              </div>
            )}
            {weeklyStats && weeklyStats.total_plays > 0 && (
              <div className="flex items-center gap-2 bg-white/15 backdrop-blur-sm rounded-lg px-3 py-2">
                <Headphones className="w-4 h-4 text-blue-300" />
                <span className="text-white text-sm font-medium">
                  {weeklyStats.total_plays} plays this week
                </span>
              </div>
            )}
            {weeklyStats && weeklyStats.unique_artists > 0 && (
              <div className="flex items-center gap-2 bg-white/15 backdrop-blur-sm rounded-lg px-3 py-2">
                <TrendingUp className="w-4 h-4 text-green-300" />
                <span className="text-white text-sm font-medium">
                  {weeklyStats.unique_artists} artists
                </span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4">
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
          icon={<BarChart3 className="w-5 h-5" />}
          title="Your Stats"
          description="Insights & trends"
          href="/stats"
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
          <div className="flex gap-4 overflow-x-auto pb-4 -mx-4 px-4 sm:-mx-6 sm:px-6 scrollbar-hide">
            {recentAlbums.map((album: any) => (
              <AlbumCard
                key={album.id}
                album={album}
                onClick={() => handlePreview({ ...album, type: 'album' })}
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
            <div className="flex gap-4 overflow-x-auto pb-4 -mx-4 px-4 sm:-mx-6 sm:px-6 scrollbar-hide">
              {section.type === 'artist_list'
                ? section.items.map((artist: any) => (
                    <ArtistCard
                      key={artist.id}
                      artist={artist}
                      onClick={() => handlePreview({ ...artist, type: 'artist' })}
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
                  ))
                : section.items.map((album: any) => (
                    <AlbumCard
                      key={album.id}
                      album={album}
                      onClick={() => handlePreview({ ...album, type: 'album' })}
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
            <Link href="/settings" className="btn-primary">
              Connect Plex Library
            </Link>
          }
        />
      )}

      {/* Preview Modal */}
      <PreviewModal
        item={previewItem}
        onClose={() => setPreviewItem(null)}
        onAdd={handleAdd}
      />
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
    <Link
      href={href}
      className="card-hover p-3 sm:p-4 flex items-center gap-3 sm:gap-4"
    >
      <div
        className={`w-10 h-10 sm:w-12 sm:h-12 rounded-lg bg-gradient-to-br ${color} flex items-center justify-center text-white flex-shrink-0 shadow-lg`}
      >
        {icon}
      </div>
      <div className="min-w-0">
        <h3 className="font-semibold text-white truncate text-sm sm:text-base">{title}</h3>
        <p className="text-xs sm:text-sm text-surface-400 truncate">{description}</p>
      </div>
    </Link>
  )
}

function getTimeOfDay(): string {
  const hour = new Date().getHours()
  if (hour < 12) return 'morning'
  if (hour < 17) return 'afternoon'
  return 'evening'
}
