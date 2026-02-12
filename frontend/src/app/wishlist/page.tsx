'use client'

import Image from 'next/image'
import Link from 'next/link'
import { useEffect, useRef, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Heart,
  Search,
  Trash2,
  MoreVertical,
  Loader2,
  Disc,
  Music,
  User,
  ListMusic,
} from 'lucide-react'
import { wishlistApi, type WishlistItem } from '@/lib/api'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { LoadingPage } from '@/components/ui/LoadingSpinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { cn, formatDate } from '@/lib/utils'
import toast from 'react-hot-toast'

type FilterStatus = 'all' | 'wanted' | 'searching' | 'found' | 'downloading' | 'downloaded' | 'failed'

export default function WishlistPage() {
  const [filterStatus, setFilterStatus] = useState<FilterStatus>('all')
  const queryClient = useQueryClient()
  const previousStatuses = useRef<Record<number, string>>({})

  const { data, isLoading } = useQuery({
    queryKey: ['wishlist', filterStatus],
    queryFn: () =>
      wishlistApi.list(filterStatus !== 'all' ? { status: filterStatus } : undefined),
    refetchInterval: (query) => {
      const items = (query.state.data as any)?.data || []
      const active = items.some((item: WishlistItem) => ['searching', 'downloading', 'importing', 'queued'].includes(item.status))
      return active ? 3000 : false
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => wishlistApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['wishlist'] })
      toast.success('Item removed from wishlist')
    },
  })

  const searchMutation = useMutation({
    mutationFn: (id: number) => wishlistApi.search(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['wishlist'] })
    },
    onError: (error: any) => {
      const detail = error?.response?.data?.detail
      toast.error(detail || 'Search unavailable. Check indexer settings and try again.')
    }
  })

  const searchAllMutation = useMutation({
    mutationFn: () => wishlistApi.searchAll(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['wishlist'] })
    },
    onError: (error: any) => {
      const detail = error?.response?.data?.detail
      toast.error(detail || 'Bulk search unavailable. Check indexer settings and try again.')
    }
  })

  const items = data?.data || []


  const activeSearchCount = items.filter((item: WishlistItem) => item.status === 'searching').length

  const statusCounts = items.reduce(
    (acc: Record<string, number>, item: WishlistItem) => {
      acc[item.status] = (acc[item.status] || 0) + 1
      return acc
    },
    {}
  )

  useEffect(() => {
    const previous = previousStatuses.current
    for (const item of items) {
      const priorStatus = previous[item.id]
      if (priorStatus === 'searching' && item.status !== 'searching') {
        const itemLabel = item.album_title || item.artist_name || 'Wishlist item'
        if (item.status === 'found') {
          toast.success(`Found a result for ${itemLabel}`)
        } else if (item.status === 'wanted') {
          toast(`No matches found yet for ${itemLabel}`, { icon: 'ℹ️' })
        } else if (item.status === 'failed') {
          toast.error(`Search failed for ${itemLabel}`)
        }
      }
      previous[item.id] = item.status
    }
  }, [items])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Wishlist</h1>
          <p className="text-surface-400 mt-1">
            {items.length} items in your wishlist
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => searchAllMutation.mutate()}
            disabled={searchAllMutation.isPending}
            className="btn-secondary"
          >
            <Search className="w-4 h-4" />
            Search All
          </button>
        </div>
      </div>

      {/* Status Filters */}
      <div className="flex items-center gap-2 overflow-x-auto pb-2">
        {(['all', 'wanted', 'searching', 'found', 'downloading', 'downloaded', 'failed'] as const).map(
          (status) => (
            <button
              key={status}
              onClick={() => setFilterStatus(status)}
              className={cn(
                'px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors',
                filterStatus === status
                  ? 'bg-primary-500/20 text-primary-400'
                  : 'text-surface-400 hover:text-white hover:bg-surface-800'
              )}
            >
              {status.charAt(0).toUpperCase() + status.slice(1)}
              {status !== 'all' && statusCounts[status] && (
                <span className="ml-2 text-xs opacity-60">
                  ({statusCounts[status]})
                </span>
              )}
            </button>
          )
        )}
      </div>


      {activeSearchCount > 0 && (
        <div className="rounded-lg border border-primary-500/30 bg-primary-500/10 px-4 py-3 text-sm text-primary-200 flex items-center gap-2">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span>
            {activeSearchCount} wishlist {activeSearchCount === 1 ? 'item is' : 'items are'} currently being searched across indexers. This updates automatically.
          </span>
        </div>
      )}

      {/* Content */}
      {isLoading ? (
        <LoadingPage message="Loading wishlist..." />
      ) : items.length > 0 ? (
        <div className="bg-surface-900 rounded-xl border border-surface-800 overflow-visible divide-y divide-surface-800">
          {items.map((item: WishlistItem) => (
            <WishlistItemRow
              key={item.id}
              item={item}
              onSearch={() => searchMutation.mutate(item.id)}
              onDelete={() => deleteMutation.mutate(item.id)}
            />
          ))}
        </div>
      ) : (
        <EmptyState
          icon={<Heart className="w-8 h-8" />}
          title="Wishlist is empty"
          description="Search for albums and add them to your wishlist"
          action={
            <Link
              href="/search"
              className="btn-primary inline-flex items-center gap-2"
            >
              <Search className="w-4 h-4" />
              Search for Music
            </Link>
          }
        />
      )}
    </div>
  )
}

const ITEM_TYPE_CONFIG: Record<string, { label: string; icon: React.ComponentType<any>; className: string }> = {
  artist: { label: 'Artist', icon: User, className: 'bg-purple-500/20 text-purple-400' },
  album: { label: 'Album', icon: Disc, className: 'bg-blue-500/20 text-blue-400' },
  track: { label: 'Track', icon: Music, className: 'bg-green-500/20 text-green-400' },
  playlist: { label: 'Playlist', icon: ListMusic, className: 'bg-orange-500/20 text-orange-400' },
}

function ItemTypeBadge({ type }: { type: string }) {
  const config = ITEM_TYPE_CONFIG[type] || ITEM_TYPE_CONFIG.album
  const Icon = config.icon
  return (
    <span className={cn('inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wide flex-shrink-0', config.className)}>
      <Icon className="w-3 h-3" />
      {config.label}
    </span>
  )
}

function WishlistItemRow({
  item,
  onSearch,
  onDelete,
}: {
  item: WishlistItem
  onSearch: () => void
  onDelete: () => void
}) {
  const [showMenu, setShowMenu] = useState(false)
  const [imageFailed, setImageFailed] = useState(false)
  const normalizedImageUrl = (item.image_url || '').replace(/^http:\/\//i, 'https://')

  return (
    <div className="flex items-center justify-between p-4 hover:bg-surface-800/50 transition-colors">
      <div className="flex items-center gap-4 min-w-0 flex-1">
        <div className="w-12 h-12 bg-surface-700 rounded flex-shrink-0 flex items-center justify-center text-surface-500 overflow-hidden">
          {normalizedImageUrl && !imageFailed ? (
            <Image
              src={normalizedImageUrl}
              alt={item.album_title || item.artist_name || 'Wishlist item artwork'}
              width={48}
              height={48}
              className="w-full h-full object-cover"
              onError={() => setImageFailed(true)}
            />
          ) : (
            <Heart className="w-5 h-5" />
          )}
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <ItemTypeBadge type={item.item_type} />
            <span className="font-medium text-white truncate">
              {item.album_title || item.artist_name}
            </span>
            <StatusBadge status={item.status} />
          </div>
          <div className="flex items-center gap-2 text-sm text-surface-400">
            {item.artist_name && item.album_title && (
              <span className="truncate">{item.artist_name}</span>
            )}
            <span>&middot;</span>
            <span>Added {formatDate(item.created_at)}</span>
            {item.auto_download && (
              <>
                <span>&middot;</span>
                <span className="text-green-400">Auto-download</span>
              </>
            )}
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2">
        {item.status === 'wanted' && (
          <button onClick={onSearch} className="btn-ghost p-2" title="Search">
            <Search className="w-4 h-4" />
          </button>
        )}
        <div className="relative z-30">
          <button
            onClick={() => setShowMenu(!showMenu)}
            className="btn-ghost p-2"
          >
            <MoreVertical className="w-4 h-4" />
          </button>
          {showMenu && (
            <>
              <div
                className="fixed inset-0 z-10"
                onClick={() => setShowMenu(false)}
              />
              <div className="absolute right-0 top-full mt-1 w-48 bg-surface-800 border border-surface-700 rounded-lg shadow-lg z-40 py-1">
                <button
                  onClick={() => {
                    onSearch()
                    setShowMenu(false)
                  }}
                  className="w-full px-4 py-2 text-left text-sm hover:bg-surface-700 transition-colors flex items-center gap-2"
                >
                  <Search className="w-4 h-4" />
                  Search Now
                </button>
                <button
                  onClick={() => {
                    onDelete()
                    setShowMenu(false)
                  }}
                  className="w-full px-4 py-2 text-left text-sm text-red-400 hover:bg-surface-700 transition-colors flex items-center gap-2"
                >
                  <Trash2 className="w-4 h-4" />
                  Remove
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
