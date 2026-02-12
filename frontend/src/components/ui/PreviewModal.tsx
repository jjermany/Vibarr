'use client'

import { useEffect, useState } from 'react'
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
import { searchApi } from '@/lib/api'
import type { PreviewData, SearchResult } from '@/lib/api'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { formatNumber, getInitials } from '@/lib/utils'

interface PreviewModalProps {
  item: SearchResult | null
  onClose: () => void
  onAdd: (item: SearchResult) => void
}

export function PreviewModal({ item, onClose, onAdd }: PreviewModalProps) {
  const [activeItem, setActiveItem] = useState<SearchResult | null>(item)
  const [headerImageFailed, setHeaderImageFailed] = useState(false)
  const [avatarImageFailed, setAvatarImageFailed] = useState(false)
  const [topAlbumImageFailures, setTopAlbumImageFailures] = useState<Record<string, boolean>>({})

  useEffect(() => {
    setActiveItem(item)
  }, [item])

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
    if (activeItem) {
      document.body.style.overflow = 'hidden'
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [activeItem])

  const { data: previewData, isLoading } = useQuery({
    queryKey: ['preview', activeItem?.type, activeItem?.name, activeItem?.artist_name, activeItem?.source],
    queryFn: () => {
      if (!activeItem) return null
      return searchApi.preview(
        activeItem.type,
        activeItem.name,
        activeItem.artist_name,
        activeItem.source
      )
    },
    enabled: !!activeItem,
  })

  const preview: PreviewData | undefined = previewData?.data

  useEffect(() => {
    setHeaderImageFailed(false)
    setAvatarImageFailed(false)
    setTopAlbumImageFailures({})
  }, [activeItem?.id, preview?.image_url, preview?.top_albums])

  if (!activeItem) return null

  const normalizedPreviewImageUrl = (activeItem.image_url || preview?.image_url || '').replace(/^http:\/\//i, 'https://')
  const isPreviewExternalImage = /^https?:\/\//i.test(normalizedPreviewImageUrl)

  const buildAlbumPreviewItem = (album: PreviewData['top_albums'][number], index: number): SearchResult => {
    const sourceAlbumId = album.source_album_id || album.source_provider_id || `${album.title}-${index}`
    const artistName = album.artist_name || (activeItem.type === 'artist' ? activeItem.name : activeItem.artist_name)
    const externalIds: Record<string, string> = {}

    if (activeItem.source === 'deezer' && album.source_provider_id) {
      externalIds.deezer_id = album.source_provider_id
    }
    if (activeItem.source === 'ytmusic' && album.source_provider_id) {
      externalIds.ytmusic_browse_id = album.source_provider_id
    }
    if (activeItem.source === 'lastfm') {
      externalIds.lastfm_album_ref = album.source_provider_id || `${artistName || 'unknown'}:${album.title}`
    }
    if (activeItem.source === 'local' && album.source_provider_id) {
      externalIds.local_album_id = album.source_provider_id
    }

    return {
      id: `${activeItem.source}:${sourceAlbumId}`,
      type: 'album',
      name: album.title,
      artist_name: artistName,
      image_url: album.image_url || preview?.image_url || activeItem.image_url,
      source: activeItem.source,
      in_library: false,
      external_ids: externalIds,
    }
  }

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
          {normalizedPreviewImageUrl && !headerImageFailed && (
            <div className="absolute inset-0 overflow-hidden">
              <Image
                src={normalizedPreviewImageUrl}
                alt=""
                fill
                className="object-cover blur-2xl opacity-30 scale-110"
                unoptimized={isPreviewExternalImage}
                onError={() => setHeaderImageFailed(true)}
              />
            </div>
          )}

          <div className="relative p-6 flex gap-5">
            <div className={`flex-shrink-0 ${activeItem.type === 'artist' ? 'w-28 h-28 rounded-full' : 'w-28 h-28 rounded-lg'} overflow-hidden bg-surface-800`}>
              {normalizedPreviewImageUrl && !avatarImageFailed ? (
                <Image
                  src={normalizedPreviewImageUrl}
                  alt={activeItem.name}
                  width={112}
                  height={112}
                  className="w-full h-full object-cover"
                  unoptimized={isPreviewExternalImage}
                  onError={() => setAvatarImageFailed(true)}
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-2xl font-bold text-surface-500">
                  {activeItem.type === 'artist' ? getInitials(activeItem.name) : <Music className="w-10 h-10" />}
                </div>
              )}
            </div>

            <div className="flex-1 min-w-0 flex flex-col justify-center">
              <span className="text-xs font-medium text-primary-400 uppercase tracking-wider mb-1">
                {activeItem.type} {activeItem.source !== 'local' && `\u00b7 ${activeItem.source === 'deezer' ? 'Deezer' : activeItem.source === 'ytmusic' ? 'YouTube Music' : activeItem.source}`}
              </span>
              <h2 className="text-xl font-bold text-white line-clamp-2">{activeItem.name}</h2>
              {activeItem.artist_name && (
                <p className="text-sm text-surface-300 mt-1">{activeItem.artist_name}</p>
              )}
              {activeItem.year && (
                <p className="text-sm text-surface-400 mt-0.5">{activeItem.year}</p>
              )}

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

            <button
              onClick={onClose}
              className="absolute top-4 right-4 p-2 text-surface-400 hover:text-white hover:bg-surface-700 rounded-lg transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        <div className="px-6 pb-6 overflow-y-auto max-h-[calc(85vh-200px)]">
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <LoadingSpinner size="md" />
            </div>
          ) : (
            <div className="space-y-5">
              {preview?.bio && (
                <div>
                  <p
                    className="text-sm text-surface-300 leading-relaxed line-clamp-4"
                    dangerouslySetInnerHTML={{ __html: preview.bio }}
                  />
                </div>
              )}

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

              {preview?.top_albums && preview.top_albums.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <Disc className="w-4 h-4 text-surface-400" />
                    <h3 className="text-sm font-medium text-surface-300">Top Albums</h3>
                  </div>
                  <div className="grid grid-cols-3 gap-3">
                    {preview.top_albums.map((album, i) => {
                      const albumKey = `${album.source_album_id || album.title}-${i}`
                      const normalizedAlbumImageUrl = (album.image_url || '').replace(/^http:\/\//i, 'https://')
                      const isExternalAlbumImage = /^https?:\/\//i.test(normalizedAlbumImageUrl)
                      const albumImageFailed = !!topAlbumImageFailures[albumKey]

                      return (
                        <button
                          key={albumKey}
                          type="button"
                          onClick={() => setActiveItem(buildAlbumPreviewItem(album, i))}
                          className="flex flex-col gap-1.5 text-left group"
                          title={`Preview ${album.title}`}
                        >
                          <div className="aspect-square rounded-lg overflow-hidden bg-surface-800 ring-1 ring-transparent group-hover:ring-primary-500 transition-colors">
                            {normalizedAlbumImageUrl && !albumImageFailed ? (
                              <Image
                                src={normalizedAlbumImageUrl}
                                alt={album.title}
                                width={120}
                                height={120}
                                className="w-full h-full object-cover"
                                unoptimized={isExternalAlbumImage}
                                onError={() => setTopAlbumImageFailures((prev) => ({ ...prev, [albumKey]: true }))}
                              />
                            ) : (
                              <div className="w-full h-full flex items-center justify-center text-surface-600">
                                <Music className="w-8 h-8" />
                              </div>
                            )}
                          </div>
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-xs text-surface-300 line-clamp-1 group-hover:text-white transition-colors">{album.title}</span>
                            {!activeItem.in_library && (
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.preventDefault()
                                  e.stopPropagation()
                                  onAdd(buildAlbumPreviewItem(album, i))
                                }}
                                className="p-1 text-surface-400 group-hover:text-white hover:bg-surface-700 rounded"
                                title="Add album"
                              >
                                <Plus className="w-3.5 h-3.5" />
                              </button>
                            )}
                          </div>
                        </button>
                      )
                    })}
                  </div>
                </div>
              )}

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
                        {!activeItem.in_library && (
                          <button
                            onClick={() => onAdd({
                              id: `preview-track-${activeItem.name}-${track.title}`,
                              type: 'track',
                              name: track.title,
                              artist_name: activeItem.type === 'artist' ? activeItem.name : activeItem.artist_name,
                              album_name: activeItem.type === 'album' ? activeItem.name : undefined,
                              image_url: activeItem.image_url || preview?.image_url,
                              source: activeItem.source,
                              in_library: false,
                              external_ids: {},
                            } as SearchResult)}
                            className="p-1 text-surface-400 hover:text-white hover:bg-surface-700 rounded"
                            title="Add track"
                          >
                            <Plus className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

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
                View on {activeItem.source === 'lastfm' ? 'Last.fm' : activeItem.source}
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
            {activeItem.in_library ? (
              <button
                disabled
                className="flex items-center gap-2 px-4 py-2 bg-green-500/20 text-green-400 rounded-lg text-sm font-medium"
              >
                <Check className="w-4 h-4" />
                In Library
              </button>
            ) : (
              <button
                onClick={() => onAdd(activeItem)}
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
