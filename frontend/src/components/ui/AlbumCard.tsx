'use client'

import Image from 'next/image'
import { Play, Plus, Check, Music } from 'lucide-react'
import { useState } from 'react'
import { cn } from '@/lib/utils'

interface AlbumLike {
  id: number | string
  title?: string
  name?: string
  cover_url?: string
  image_url?: string
  artist_name?: string
  release_year?: number
  year?: number
  in_library?: boolean
  source?: string
}

interface AlbumCardProps {
  album: AlbumLike
  showArtist?: boolean
  size?: 'sm' | 'md' | 'lg'
  onClick?: () => void
  onAdd?: () => void
}

export function AlbumCard({ album, showArtist = true, size = 'md', onClick, onAdd }: AlbumCardProps) {
  const sizes = {
    sm: 'w-32',
    md: 'w-40',
    lg: 'w-48',
  }

  // Normalize field names (SearchResult uses name/image_url/year, Album uses title/cover_url/release_year)
  const title = album.title || album.name || ''
  const coverUrl = album.cover_url || album.image_url
  const artistName = album.artist_name
  const year = album.release_year || album.year
  const inLibrary = album.in_library ?? false
  const [imageFailed, setImageFailed] = useState(false)
  const normalizedCoverUrl = (coverUrl || '').replace(/^http:\/\//i, 'https://')
  const isExternalImage = /^https?:\/\//i.test(normalizedCoverUrl)

  const handleClick = (e: React.MouseEvent) => {
    if (onClick) {
      e.preventDefault()
      onClick()
    }
  }

  const handleAdd = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (onAdd) onAdd()
  }

  return (
    <div
      onClick={handleClick}
      className={cn(
        'group flex flex-col cursor-pointer',
        sizes[size]
      )}
    >
      {/* Cover */}
      <div className="relative aspect-square rounded-lg overflow-hidden bg-surface-800 mb-3">
        {normalizedCoverUrl && !imageFailed ? (
          <Image
            src={normalizedCoverUrl}
            alt={title}
            fill
            className="object-cover transition-transform group-hover:scale-105"
            unoptimized={isExternalImage}
            onError={() => setImageFailed(true)}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-surface-600">
            <Music className="w-12 h-12" />
          </div>
        )}

        {/* Hover overlay */}
        <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
          <button className="p-2 bg-primary-500 rounded-full hover:bg-primary-600 transition-colors">
            <Play className="w-5 h-5 text-white" fill="white" />
          </button>
          {onAdd && (
            <button
              onClick={handleAdd}
              className="p-2 bg-surface-700 rounded-full hover:bg-surface-600 transition-colors"
            >
              {inLibrary ? (
                <Check className="w-5 h-5 text-green-400" />
              ) : (
                <Plus className="w-5 h-5 text-white" />
              )}
            </button>
          )}
        </div>

        {/* In library indicator */}
        {inLibrary && (
          <div className="absolute top-2 right-2 p-1 bg-green-500 rounded-full">
            <Check className="w-3 h-3 text-white" />
          </div>
        )}

        {/* Source badge for external items */}
        {album.source && (
          <div className="absolute top-2 left-2 px-1.5 py-0.5 bg-black/60 backdrop-blur-sm rounded text-[10px] font-medium text-surface-300">
            {album.source === 'lastfm' ? 'Last.fm' : album.source === 'local' ? 'Local' : album.source}
          </div>
        )}
      </div>

      {/* Info */}
      <div className="flex flex-col gap-0.5 min-w-0">
        <span className="text-sm font-medium text-white line-clamp-1 group-hover:text-primary-400 transition-colors">
          {title}
        </span>
        {showArtist && artistName && (
          <span className="text-xs text-surface-400 line-clamp-1">
            {artistName}
          </span>
        )}
        {year && (
          <span className="text-xs text-surface-500">{year}</span>
        )}
      </div>
    </div>
  )
}
