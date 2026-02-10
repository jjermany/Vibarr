'use client'

import { useEffect } from 'react'
import Image from 'next/image'
import { useQuery } from '@tanstack/react-query'
import {
  X,
  Plus,
  Check,
  Users,
  Headphones,
  Tag,
  ExternalLink,
  Music,
  Disc,
} from 'lucide-react'
import { searchApi, wishlistApi } from '@/lib/api'
import type { PreviewData, SearchResult } from '@/lib/api'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { formatNumber, getInitials } from '@/lib/utils'

interface PreviewModalProps {
  item: SearchResult | null
  onClose: () => void
  onAdd: (item: SearchResult) => void
}

export function PreviewModal({ item, onClose, onAdd }: PreviewModalProps) {
  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  // Prevent body scroll when modal is open
  useEffect(() => {
    if (item) {
      document.body.style.overflow = 'hidden'
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [item])

  const { data: previewData, isLoading } = useQuery({
    queryKey: ['preview', item?.type, item?.name, item?.artist_name, item?.source],
    queryFn: () => {
      if (!item) return null
      return searchApi.preview(
        item.type,
        item.name,
        item.artist_name,
        item.source
      )
    },
    enabled: !!item,
  })

  if (!item) return null

  const preview: PreviewData | undefined = previewData?.data

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />

      {/* Modal */}
      <div
        className="relative bg-surface-900 border border-surface-700 rounded-2xl w-full max-w-2xl max-h-[85vh] overflow-hidden shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header with image */}
        <div className="relative">
          {/* Background blur image */}
          {(item.image_url || preview?.image_url) && (
            <div className="absolute inset-0 overflow-hidden">
              <Image
                src={item.image_url || preview?.image_url || ''}
                alt=""
                fill
                className="object-cover blur-2xl opacity-30 scale-110"
              />
            </div>
          )}

          <div className="relative p-6 flex gap-5">
            {/* Image / Avatar */}
            <div className={`flex-shrink-0 ${item.type === 'artist' ? 'w-28 h-28 rounded-full' : 'w-28 h-28 rounded-lg'} overflow-hidden bg-surface-800`}>
              {(item.image_url || preview?.image_url) ? (
                <Image
                  src={item.image_url || preview?.image_url || ''}
                  alt={item.name}
                  width={112}
                  height={112}
                  className="w-full h-full object-cover"
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-2xl font-bold text-surface-500">
                  {item.type === 'artist' ? (
                    getInitials(item.name)
                  ) : (
                    <Music className="w-10 h-10" />
                  )}
                </div>
              )}
            </div>

            {/* Basic info */}
            <div className="flex-1 min-w-0 flex flex-col justify-center">
              <span className="text-xs font-medium text-primary-400 uppercase tracking-wider mb-1">
                {item.type} {item.source !== 'local' && `\u00b7 ${item.source}`}
              </span>
              <h2 className="text-xl font-bold text-white line-clamp-2">{item.name}</h2>
              {item.artist_name && (
                <p className="text-sm text-surface-300 mt-1">{item.artist_name}</p>
              )}
              {item.year && (
                <p className="text-sm text-surface-400 mt-0.5">{item.year}</p>
              )}

              {/* Stats */}
              {preview && (preview.listeners || preview.playcount) && (
                <div className="flex items-center gap-4 mt-3">
                  {preview.listeners && (
                    <div className="flex items-center gap-1.5 text-xs text-surface-400">
                      <Users className="w-3.5 h-3.5" />
                      <span>{formatNumber(preview.listeners)} listeners</span>
                    </div>
                  )}
                  {preview.playcount && (
                    <div className="flex items-center gap-1.5 text-xs text-surface-400">
                      <Headphones className="w-3.5 h-3.5" />
                      <span>{formatNumber(preview.playcount)} plays</span>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Close button */}
            <button
              onClick={onClose}
              className="absolute top-4 right-4 p-2 text-surface-400 hover:text-white hover:bg-surface-700 rounded-lg transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="px-6 pb-6 overflow-y-auto max-h-[calc(85vh-200px)]">
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <LoadingSpinner size="md" />
            </div>
          ) : (
            <div className="space-y-5">
              {/* Bio */}
              {preview?.bio && (
                <div>
                  <p
                    className="text-sm text-surface-300 leading-relaxed line-clamp-4"
                    dangerouslySetInnerHTML={{ __html: preview.bio }}
                  />
                </div>
              )}

              {/* Tags */}
              {preview?.tags && preview.tags.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <Tag className="w-4 h-4 text-surface-400" />
                    <h3 className="text-sm font-medium text-surface-300">Tags</h3>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {preview.tags.map((tag) => (
                      <span
                        key={tag}
                        className="px-2.5 py-1 text-xs bg-surface-800 text-surface-300 rounded-full"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Top Albums (for artist preview) */}
              {preview?.top_albums && preview.top_albums.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <Disc className="w-4 h-4 text-surface-400" />
                    <h3 className="text-sm font-medium text-surface-300">Top Albums</h3>
                  </div>
                  <div className="grid grid-cols-3 gap-3">
                    {preview.top_albums.map((album) => (
                      <div key={album.title} className="flex flex-col gap-1.5">
                        <div className="aspect-square rounded-lg overflow-hidden bg-surface-800">
                          {album.image_url ? (
                            <Image
                              src={album.image_url}
                              alt={album.title}
                              width={120}
                              height={120}
                              className="w-full h-full object-cover"
                            />
                          ) : (
                            <div className="w-full h-full flex items-center justify-center text-surface-600">
                              <Music className="w-8 h-8" />
                            </div>
                          )}
                        </div>
                        <span className="text-xs text-surface-300 line-clamp-1">{album.title}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Track list (for album preview) */}
              {preview?.tracks && preview.tracks.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <Music className="w-4 h-4 text-surface-400" />
                    <h3 className="text-sm font-medium text-surface-300">Tracks</h3>
                  </div>
                  <div className="bg-surface-800/50 rounded-lg divide-y divide-surface-700/50">
                    {preview.tracks.map((track, i) => (
                      <div
                        key={`${track.title}-${i}`}
                        className="flex items-center gap-3 px-3 py-2"
                      >
                        <span className="w-5 text-center text-xs text-surface-500">
                          {track.track_number || i + 1}
                        </span>
                        <span className="text-sm text-surface-300 flex-1 truncate">
                          {track.title}
                        </span>
                        {track.duration && track.duration > 0 && (
                          <span className="text-xs text-surface-500">
                            {Math.floor(track.duration / 60000)}:{String(Math.floor((track.duration % 60000) / 1000)).padStart(2, '0')}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer actions */}
        <div className="border-t border-surface-700 px-6 py-4 flex items-center justify-between bg-surface-900">
          <div className="flex items-center gap-2">
            {preview?.url && (
              <a
                href={preview.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 px-3 py-2 text-sm text-surface-400 hover:text-white transition-colors"
              >
                <ExternalLink className="w-4 h-4" />
                View on {item.source === 'lastfm' ? 'Last.fm' : item.source}
              </a>
            )}
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm text-surface-400 hover:text-white transition-colors"
            >
              Close
            </button>
            {item.in_library ? (
              <button
                disabled
                className="flex items-center gap-2 px-4 py-2 bg-green-500/20 text-green-400 rounded-lg text-sm font-medium"
              >
                <Check className="w-4 h-4" />
                In Library
              </button>
            ) : (
              <button
                onClick={() => onAdd(item)}
                className="flex items-center gap-2 px-4 py-2 bg-primary-500 hover:bg-primary-600 text-white rounded-lg text-sm font-medium transition-colors"
              >
                <Plus className="w-4 h-4" />
                Add to Library
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
