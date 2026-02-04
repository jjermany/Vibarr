'use client'

import Image from 'next/image'
import Link from 'next/link'
import { Play, Check } from 'lucide-react'
import { cn, getInitials } from '@/lib/utils'
import type { Artist } from '@/lib/api'

interface ArtistCardProps {
  artist: Artist
  size?: 'sm' | 'md' | 'lg'
}

export function ArtistCard({ artist, size = 'md' }: ArtistCardProps) {
  const sizes = {
    sm: 'w-28',
    md: 'w-36',
    lg: 'w-44',
  }

  return (
    <Link
      href={`/artists/${artist.id}`}
      className={cn('group flex flex-col items-center', sizes[size])}
    >
      {/* Avatar */}
      <div className="relative w-full aspect-square rounded-full overflow-hidden bg-surface-800 mb-3">
        {artist.image_url ? (
          <Image
            src={artist.image_url}
            alt={artist.name}
            fill
            className="object-cover transition-transform group-hover:scale-105"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-2xl font-bold text-surface-600">
            {getInitials(artist.name)}
          </div>
        )}

        {/* Hover overlay */}
        <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
          <button className="p-3 bg-primary-500 rounded-full hover:bg-primary-600 transition-colors">
            <Play className="w-6 h-6 text-white" fill="white" />
          </button>
        </div>

        {/* In library indicator */}
        {artist.in_library && (
          <div className="absolute bottom-2 right-2 p-1.5 bg-green-500 rounded-full">
            <Check className="w-3 h-3 text-white" />
          </div>
        )}
      </div>

      {/* Info */}
      <div className="flex flex-col items-center text-center gap-0.5">
        <span className="text-sm font-medium text-white line-clamp-1 group-hover:text-primary-400 transition-colors">
          {artist.name}
        </span>
        <span className="text-xs text-surface-400">Artist</span>
      </div>
    </Link>
  )
}
