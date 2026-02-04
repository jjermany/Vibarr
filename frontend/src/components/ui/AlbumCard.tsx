'use client'

import Image from 'next/image'
import Link from 'next/link'
import { Play, Heart, Plus, Check } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { Album } from '@/lib/api'

interface AlbumCardProps {
  album: Album
  showArtist?: boolean
  size?: 'sm' | 'md' | 'lg'
}

export function AlbumCard({ album, showArtist = true, size = 'md' }: AlbumCardProps) {
  const sizes = {
    sm: 'w-32',
    md: 'w-40',
    lg: 'w-48',
  }

  return (
    <Link
      href={`/albums/${album.id}`}
      className={cn('group flex flex-col', sizes[size])}
    >
      {/* Cover */}
      <div className="relative aspect-square rounded-lg overflow-hidden bg-surface-800 mb-3">
        {album.cover_url ? (
          <Image
            src={album.cover_url}
            alt={album.title}
            fill
            className="object-cover transition-transform group-hover:scale-105"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-surface-600">
            <svg className="w-12 h-12" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z" />
            </svg>
          </div>
        )}

        {/* Hover overlay */}
        <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
          <button className="p-2 bg-primary-500 rounded-full hover:bg-primary-600 transition-colors">
            <Play className="w-5 h-5 text-white" fill="white" />
          </button>
          <button className="p-2 bg-surface-700 rounded-full hover:bg-surface-600 transition-colors">
            {album.in_library ? (
              <Check className="w-5 h-5 text-green-400" />
            ) : (
              <Plus className="w-5 h-5 text-white" />
            )}
          </button>
        </div>

        {/* In library indicator */}
        {album.in_library && (
          <div className="absolute top-2 right-2 p-1 bg-green-500 rounded-full">
            <Check className="w-3 h-3 text-white" />
          </div>
        )}
      </div>

      {/* Info */}
      <div className="flex flex-col gap-0.5 min-w-0">
        <span className="text-sm font-medium text-white line-clamp-1 group-hover:text-primary-400 transition-colors">
          {album.title}
        </span>
        {showArtist && album.artist_name && (
          <span className="text-xs text-surface-400 line-clamp-1">
            {album.artist_name}
          </span>
        )}
        {album.release_year && (
          <span className="text-xs text-surface-500">{album.release_year}</span>
        )}
      </div>
    </Link>
  )
}
