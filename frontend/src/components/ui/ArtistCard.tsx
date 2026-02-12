'use client'

import Image from 'next/image'
import { Plus, Check } from 'lucide-react'
import { useState } from 'react'
import { cn, getInitials } from '@/lib/utils'

interface ArtistLike {
  id: number | string
  name: string
  image_url?: string
  in_library?: boolean
  source?: string
}

interface ArtistCardProps {
  artist: ArtistLike
  size?: 'sm' | 'md' | 'lg'
  onClick?: () => void
  onAdd?: () => void
}

export function ArtistCard({ artist, size = 'md', onClick, onAdd }: ArtistCardProps) {
  const sizes = {
    sm: 'w-28',
    md: 'w-36',
    lg: 'w-44',
  }

  const inLibrary = artist.in_library ?? false
  const [imageFailed, setImageFailed] = useState(false)
  const normalizedImageUrl = (artist.image_url || '').replace(/^http:\/\//i, 'https://')
  const isExternalImage = /^https?:\/\//i.test(normalizedImageUrl)

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
      className={cn('group flex flex-col items-center cursor-pointer', sizes[size])}
    >
      {/* Avatar */}
      <div className="relative w-full aspect-square rounded-full overflow-hidden bg-surface-800 mb-3">
        {normalizedImageUrl && !imageFailed ? (
          <Image
            src={normalizedImageUrl}
            alt={artist.name}
            fill
            className="object-cover transition-transform group-hover:scale-105"
            unoptimized={isExternalImage}
            onError={() => setImageFailed(true)}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-2xl font-bold text-surface-600">
            {getInitials(artist.name)}
          </div>
        )}

        {/* Hover overlay */}
        <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
          {onAdd && (
            <button
              onClick={handleAdd}
              className="p-3 bg-surface-700 rounded-full hover:bg-surface-600 transition-colors"
              aria-label={inLibrary ? 'In library' : 'Add to library'}
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
          <div className="absolute bottom-2 right-2 p-1.5 bg-green-500 rounded-full">
            <Check className="w-3 h-3 text-white" />
          </div>
        )}

        {/* Source badge for external items */}
        {artist.source && artist.source !== 'local' && (
          <div className="absolute top-1 left-1 px-1.5 py-0.5 bg-black/60 backdrop-blur-sm rounded-full text-[10px] font-medium text-surface-300">
            {artist.source === 'lastfm' ? 'Last.fm' : artist.source}
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
    </div>
  )
}
