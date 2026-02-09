'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Download,
  Search,
  RefreshCw,
  XCircle,
  RotateCcw,
  Pause,
  Play,
  HardDrive,
  ArrowDownToLine,
  CheckCircle,
  AlertCircle,
  Clock,
  Activity,
} from 'lucide-react'
import {
  downloadsApi,
  type Download as DownloadType,
  type DownloadStats,
  type ReleaseSearchResult,
} from '@/lib/api'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { LoadingPage } from '@/components/ui/LoadingSpinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { cn, formatDate, formatBytes } from '@/lib/utils'
import toast from 'react-hot-toast'

type Tab = 'queue' | 'history' | 'search'

export default function DownloadsPage() {
  const [activeTab, setActiveTab] = useState<Tab>('queue')
  const [searchArtist, setSearchArtist] = useState('')
  const [searchAlbum, setSearchAlbum] = useState('')
  const [searchFormat, setSearchFormat] = useState('')
  const queryClient = useQueryClient()

  const { data: statsData } = useQuery({
    queryKey: ['download-stats'],
    queryFn: () => downloadsApi.stats(),
    refetchInterval: 10000,
  })

  const { data: queueData, isLoading: queueLoading } = useQuery({
    queryKey: ['download-queue'],
    queryFn: () => downloadsApi.queue(),
    refetchInterval: 5000,
    enabled: activeTab === 'queue',
  })

  const { data: historyData, isLoading: historyLoading } = useQuery({
    queryKey: ['download-history'],
    queryFn: () => downloadsApi.history(100),
    enabled: activeTab === 'history',
  })

  const cancelMutation = useMutation({
    mutationFn: (id: number) => downloadsApi.cancel(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['download-queue'] })
      queryClient.invalidateQueries({ queryKey: ['download-stats'] })
      toast.success('Download cancelled')
    },
  })

  const retryMutation = useMutation({
    mutationFn: (id: number) => downloadsApi.retry(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['download-queue'] })
      queryClient.invalidateQueries({ queryKey: ['download-history'] })
      queryClient.invalidateQueries({ queryKey: ['download-stats'] })
      toast.success('Download retry queued')
    },
  })

  const searchMutation = useMutation({
    mutationFn: () =>
      downloadsApi.search(searchArtist, searchAlbum, searchFormat || undefined),
    onError: () => {
      toast.error('Search failed - is Prowlarr configured?')
    },
  })

  const grabMutation = useMutation({
    mutationFn: (result: ReleaseSearchResult) =>
      downloadsApi.grab({
        guid: result.guid,
        indexer_id: result.indexer_id || 0,
        artist_name: searchArtist,
        album_title: searchAlbum,
        release_title: result.title,
        release_size: result.size,
        release_format: result.format || undefined,
        release_quality: result.quality || undefined,
        seeders: result.seeders,
        indexer_name: result.indexer || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['download-queue'] })
      queryClient.invalidateQueries({ queryKey: ['download-stats'] })
      toast.success('Release grabbed - download starting')
    },
    onError: () => {
      toast.error('Failed to grab release')
    },
  })

  const addMutation = useMutation({
    mutationFn: () =>
      downloadsApi.add({
        artist_name: searchArtist,
        album_title: searchAlbum,
        preferred_format: searchFormat || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['download-queue'] })
      queryClient.invalidateQueries({ queryKey: ['download-stats'] })
      toast.success('Added to download queue')
      setSearchArtist('')
      setSearchAlbum('')
    },
  })

  const stats = statsData?.data

  const queue = queueData?.data || []
  const history = historyData?.data || []
  const searchResults = searchMutation.data?.data || []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Downloads</h1>
          <p className="text-surface-400 mt-1">
            Manage your download queue and history
          </p>
        </div>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard
            icon={<Activity className="w-5 h-5 text-primary-400" />}
            label="Active"
            value={stats.downloading + stats.importing}
          />
          <StatCard
            icon={<Clock className="w-5 h-5 text-yellow-400" />}
            label="Pending"
            value={stats.pending + stats.searching}
          />
          <StatCard
            icon={<CheckCircle className="w-5 h-5 text-green-400" />}
            label="Completed"
            value={stats.completed}
          />
          <StatCard
            icon={<AlertCircle className="w-5 h-5 text-red-400" />}
            label="Failed"
            value={stats.failed}
          />
        </div>
      )}

      {/* Tabs */}
      <div className="flex items-center gap-1 border-b border-surface-800">
        {([
          { id: 'queue' as Tab, label: 'Queue', icon: ArrowDownToLine },
          { id: 'history' as Tab, label: 'History', icon: Clock },
          { id: 'search' as Tab, label: 'Manual Search', icon: Search },
        ]).map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              'flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors',
              activeTab === tab.id
                ? 'border-primary-500 text-primary-400'
                : 'border-transparent text-surface-400 hover:text-white'
            )}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
            {tab.id === 'queue' && queue.length > 0 && (
              <span className="bg-primary-500/20 text-primary-400 text-xs px-2 py-0.5 rounded-full">
                {queue.length}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === 'queue' && (
        <QueueTab
          downloads={queue}
          isLoading={queueLoading}
          onCancel={(id) => cancelMutation.mutate(id)}
          onRetry={(id) => retryMutation.mutate(id)}
        />
      )}

      {activeTab === 'history' && (
        <HistoryTab
          downloads={history}
          isLoading={historyLoading}
          onRetry={(id) => retryMutation.mutate(id)}
        />
      )}

      {activeTab === 'search' && (
        <SearchTab
          artist={searchArtist}
          album={searchAlbum}
          format={searchFormat}
          onArtistChange={setSearchArtist}
          onAlbumChange={setSearchAlbum}
          onFormatChange={setSearchFormat}
          onSearch={() => searchMutation.mutate()}
          onGrab={(result) => grabMutation.mutate(result)}
          onAddToQueue={() => addMutation.mutate()}
          isSearching={searchMutation.isPending}
          isGrabbing={grabMutation.isPending}
          hasSearched={searchMutation.isSuccess}
          results={searchResults}
        />
      )}
    </div>
  )
}

function StatCard({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode
  label: string
  value: number
}) {
  return (
    <div className="card p-4 flex items-center gap-3">
      {icon}
      <div>
        <div className="text-2xl font-bold text-white">{value}</div>
        <div className="text-xs text-surface-400">{label}</div>
      </div>
    </div>
  )
}

function QueueTab({
  downloads,
  isLoading,
  onCancel,
  onRetry,
}: {
  downloads: DownloadType[]
  isLoading: boolean
  onCancel: (id: number) => void
  onRetry: (id: number) => void
}) {
  if (isLoading) return <LoadingPage message="Loading queue..." />

  if (downloads.length === 0) {
    return (
      <EmptyState
        icon={<ArrowDownToLine className="w-8 h-8" />}
        title="Queue is empty"
        description="Add items from search or your wishlist to start downloading"
      />
    )
  }

  return (
    <div className="space-y-3">
      {downloads.map((dl) => (
        <DownloadCard
          key={dl.id}
          download={dl}
          onCancel={() => onCancel(dl.id)}
          onRetry={() => onRetry(dl.id)}
        />
      ))}
    </div>
  )
}

function HistoryTab({
  downloads,
  isLoading,
  onRetry,
}: {
  downloads: DownloadType[]
  isLoading: boolean
  onRetry: (id: number) => void
}) {
  if (isLoading) return <LoadingPage message="Loading history..." />

  if (downloads.length === 0) {
    return (
      <EmptyState
        icon={<HardDrive className="w-8 h-8" />}
        title="No download history"
        description="Completed and failed downloads will appear here"
      />
    )
  }

  return (
    <div className="space-y-3">
      {downloads.map((dl) => (
        <DownloadCard
          key={dl.id}
          download={dl}
          onRetry={dl.status === 'failed' ? () => onRetry(dl.id) : undefined}
        />
      ))}
    </div>
  )
}

function DownloadCard({
  download,
  onCancel,
  onRetry,
}: {
  download: DownloadType
  onCancel?: () => void
  onRetry?: () => void
}) {
  const isActive = ['downloading', 'searching', 'queued', 'importing'].includes(
    download.status
  )

  return (
    <div className="card p-4">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-4 min-w-0 flex-1">
          <div className="w-12 h-12 bg-surface-700 rounded flex-shrink-0 flex items-center justify-center text-surface-500">
            <Download className="w-5 h-5" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="font-medium text-white truncate">
                {download.album_title}
              </span>
              <StatusBadge status={download.status as any} />
            </div>
            <div className="flex items-center gap-2 text-sm text-surface-400 mt-0.5">
              <span className="truncate">{download.artist_name}</span>
              {download.release_quality && (
                <>
                  <span>&middot;</span>
                  <span className="uppercase text-xs font-medium text-surface-300">
                    {download.release_quality}
                  </span>
                </>
              )}
              {download.release_size && (
                <>
                  <span>&middot;</span>
                  <span>{formatBytes(download.release_size)}</span>
                </>
              )}
              {download.indexer_name && (
                <>
                  <span>&middot;</span>
                  <span>{download.indexer_name}</span>
                </>
              )}
              {download.source !== 'manual' && (
                <>
                  <span>&middot;</span>
                  <span className="capitalize">{download.source}</span>
                </>
              )}
            </div>
            {download.status_message && (
              <p className="text-xs text-surface-500 mt-1 truncate">
                {download.status_message}
              </p>
            )}
          </div>
        </div>

        {/* Progress & Actions */}
        <div className="flex items-center gap-3 flex-shrink-0">
          {download.status === 'downloading' && (
            <div className="text-right">
              <div className="text-sm font-medium text-white">
                {Math.round(download.progress)}%
              </div>
              {download.download_speed && download.download_speed > 0 && (
                <div className="text-xs text-surface-400">
                  {formatBytes(download.download_speed)}/s
                </div>
              )}
              {download.eta_seconds && download.eta_seconds > 0 && (
                <div className="text-xs text-surface-400">
                  {formatEta(download.eta_seconds)}
                </div>
              )}
            </div>
          )}

          {onCancel && isActive && (
            <button
              onClick={onCancel}
              className="btn-ghost p-2 text-red-400 hover:text-red-300"
              title="Cancel"
            >
              <XCircle className="w-4 h-4" />
            </button>
          )}

          {onRetry && (
            <button
              onClick={onRetry}
              className="btn-ghost p-2 text-surface-400 hover:text-white"
              title="Retry"
            >
              <RotateCcw className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Progress Bar */}
      {download.status === 'downloading' && download.progress > 0 && (
        <div className="mt-3 h-1.5 bg-surface-700 rounded-full overflow-hidden">
          <div
            className="h-full bg-primary-500 rounded-full transition-all duration-500"
            style={{ width: `${Math.min(download.progress, 100)}%` }}
          />
        </div>
      )}
    </div>
  )
}

function SearchTab({
  artist,
  album,
  format,
  onArtistChange,
  onAlbumChange,
  onFormatChange,
  onSearch,
  onGrab,
  onAddToQueue,
  isSearching,
  isGrabbing,
  hasSearched,
  results,
}: {
  artist: string
  album: string
  format: string
  onArtistChange: (v: string) => void
  onAlbumChange: (v: string) => void
  onFormatChange: (v: string) => void
  onSearch: () => void
  onGrab: (result: ReleaseSearchResult) => void
  onAddToQueue: () => void
  isSearching: boolean
  isGrabbing: boolean
  hasSearched: boolean
  results: ReleaseSearchResult[]
}) {
  return (
    <div className="space-y-6">
      {/* Search Form */}
      <div className="card p-6">
        <h3 className="text-lg font-semibold text-white mb-4">
          Search Indexers
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-surface-300 mb-1">
              Artist
            </label>
            <input
              type="text"
              value={artist}
              onChange={(e) => onArtistChange(e.target.value)}
              placeholder="Artist name"
              className="input w-full"
              onKeyDown={(e) =>
                e.key === 'Enter' && artist && album && onSearch()
              }
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-surface-300 mb-1">
              Album
            </label>
            <input
              type="text"
              value={album}
              onChange={(e) => onAlbumChange(e.target.value)}
              placeholder="Album title"
              className="input w-full"
              onKeyDown={(e) =>
                e.key === 'Enter' && artist && album && onSearch()
              }
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-surface-300 mb-1">
              Preferred Format
            </label>
            <select
              value={format}
              onChange={(e) => onFormatChange(e.target.value)}
              className="input w-full"
            >
              <option value="">Any</option>
              <option value="flac">FLAC</option>
              <option value="320">MP3 320</option>
              <option value="v0">MP3 V0</option>
            </select>
          </div>
        </div>
        <div className="flex items-center gap-3 mt-4">
          <button
            onClick={onSearch}
            disabled={!artist || !album || isSearching}
            className="btn-primary"
          >
            {isSearching ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              <Search className="w-4 h-4" />
            )}
            {isSearching ? 'Searching...' : 'Search Indexers'}
          </button>
          <button
            onClick={onAddToQueue}
            disabled={!artist || !album}
            className="btn-secondary"
          >
            <ArrowDownToLine className="w-4 h-4" />
            Auto-Search & Queue
          </button>
        </div>
      </div>

      {/* Search Results */}
      {results.length > 0 && (
        <div className="card">
          <div className="p-4 border-b border-surface-800">
            <h3 className="font-semibold text-white">
              {results.length} results found
            </h3>
          </div>
          <div className="divide-y divide-surface-800">
            {results.map((result, idx) => (
              <div
                key={`${result.guid}-${idx}`}
                className="p-4 flex items-center justify-between hover:bg-surface-800/50 transition-colors"
              >
                <div className="min-w-0 flex-1">
                  <div className="font-medium text-white text-sm truncate">
                    {result.title}
                  </div>
                  <div className="flex items-center gap-3 mt-1 text-xs text-surface-400">
                    {result.indexer && <span>{result.indexer}</span>}
                    {result.quality && (
                      <span className="uppercase font-medium text-surface-300">
                        {result.quality}
                      </span>
                    )}
                    <span>{formatBytes(result.size)}</span>
                    <span>
                      {result.seeders} seed{result.seeders !== 1 && 's'}
                    </span>
                    <span className="text-surface-500">
                      Score: {Math.round(result.score)}
                    </span>
                  </div>
                </div>
                <button
                  onClick={() => onGrab(result)}
                  disabled={isGrabbing}
                  className="btn-primary text-sm py-1.5 px-3 ml-4"
                >
                  <Download className="w-3.5 h-3.5" />
                  Grab
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {hasSearched && results.length === 0 && (
        <EmptyState
          icon={<Search className="w-8 h-8" />}
          title="No results found"
          description="Try adjusting your search terms or format preference"
        />
      )}
    </div>
  )
}

function formatEta(seconds: number): string {
  if (seconds <= 0) return ''
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`
  const hours = Math.floor(seconds / 3600)
  const mins = Math.floor((seconds % 3600) / 60)
  return `${hours}h ${mins}m`
}
