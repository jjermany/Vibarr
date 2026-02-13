'use client'

import { useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Download,
  Search,
  RefreshCw,
  XCircle,
  RotateCcw,
  HardDrive,
  ArrowDownToLine,
  CheckCircle,
  AlertCircle,
  Clock,
  Activity,
  Trash2,
} from 'lucide-react'
import {
  downloadsApi,
  type Download as DownloadType,
  type ReleaseSearchResult,
} from '@/lib/api'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { LoadingPage } from '@/components/ui/LoadingSpinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { cn, formatBytes } from '@/lib/utils'
import toast from 'react-hot-toast'
import { getVisibleSelectionState } from './selection'

type Tab = 'queue' | 'history' | 'search'

export default function DownloadsPage() {
  const [activeTab, setActiveTab] = useState<Tab>('queue')
  const [searchArtist, setSearchArtist] = useState('')
  const [searchAlbum, setSearchAlbum] = useState('')
  const [searchFormat, setSearchFormat] = useState('')
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
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
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: true,
    enabled: activeTab === 'queue',
  })

  const { data: historyData, isLoading: historyLoading } = useQuery({
    queryKey: ['download-history'],
    queryFn: () => downloadsApi.history(100),
    refetchInterval: activeTab === 'history' ? 10000 : false,
    refetchOnWindowFocus: true,
    enabled: activeTab === 'history',
  })

  const refreshDownloadQueries = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['download-queue'] }),
      queryClient.invalidateQueries({ queryKey: ['download-history'] }),
      queryClient.invalidateQueries({ queryKey: ['download-stats'] }),
    ])
  }

  const cancelMutation = useMutation({
    mutationFn: (id: number) => downloadsApi.cancel(id),
    onSuccess: async () => {
      await refreshDownloadQueries()
      toast.success('Download cancelled')
    },
    onError: (error: any) => {
      toast.error(error?.response?.data?.detail || 'Failed to cancel download')
    },
  })

  const retryMutation = useMutation({
    mutationFn: (id: number) => downloadsApi.retry(id),
    onSuccess: async () => {
      await refreshDownloadQueries()
      toast.success('Download retry queued')
    },
    onError: (error: any) => {
      toast.error(error?.response?.data?.detail || 'Failed to retry download')
    },
  })

  const deleteSelectedMutation = useMutation({
    mutationFn: (ids: number[]) => downloadsApi.deleteSelected(ids),
    onSuccess: async (response) => {
      const result = response.data
      await refreshDownloadQueries()
      setSelectedIds((current) => {
        const next = new Set(current)
        for (const id of result.deleted_ids || []) {
          next.delete(id)
        }
        return next
      })
      toast.success(`Deleted ${result.deleted} selected download${result.deleted === 1 ? '' : 's'}`)
      if (result.failed > 0) {
        toast.error(`${result.failed} selected download${result.failed === 1 ? '' : 's'} failed to delete`)
      }
    },
  })

  const deleteAllMutation = useMutation({
    mutationFn: (scope: 'queue' | 'history') => downloadsApi.deleteAll(scope),
    onSuccess: async (response) => {
      const result = response.data
      await refreshDownloadQueries()
      setSelectedIds(new Set())
      toast.success(`Deleted ${result.deleted} download${result.deleted === 1 ? '' : 's'}`)
      if (result.failed > 0) {
        toast.error(`${result.failed} download${result.failed === 1 ? '' : 's'} failed to delete`)
      }
    },
  })

  const searchMutation = useMutation({
    mutationFn: () =>
      downloadsApi.search(searchArtist, searchAlbum, searchFormat || undefined),
    onError: (error: any) => {
      toast.error(error?.response?.data?.detail || 'Search failed - is Prowlarr configured?')
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
        protocol: result.protocol || undefined,
        download_url: result.download_url || undefined,
      }),
    onSuccess: async () => {
      await refreshDownloadQueries()
      toast.success('Release grabbed - download starting')
    },
    onError: (error: any) => {
      toast.error(error?.response?.data?.detail || 'Failed to grab release')
    },
  })

  const addMutation = useMutation({
    mutationFn: () =>
      downloadsApi.add({
        artist_name: searchArtist,
        album_title: searchAlbum,
        preferred_format: searchFormat || undefined,
      }),
    onSuccess: async () => {
      await refreshDownloadQueries()
      toast.success('Added to download queue')
      setSearchArtist('')
      setSearchAlbum('')
    },
    onError: (error: any) => {
      toast.error(error?.response?.data?.detail || 'Failed to add to download queue')
    },
  })

  const stats = statsData?.data
  const queue = queueData?.data || []
  const history = historyData?.data || []
  const searchResults = searchMutation.data?.data || []
  const visibleDownloads = activeTab === 'queue' ? queue : history

  useEffect(() => {
    if (activeTab === 'search') {
      setSelectedIds(new Set())
      return
    }

    setSelectedIds((current) => {
      const visible = new Set(visibleDownloads.map((dl) => dl.id))
      const next = new Set<number>()
      current.forEach((id) => {
        if (visible.has(id)) {
          next.add(id)
        }
      })
      return next
    })
  }, [activeTab, visibleDownloads])

  const selectionState = getVisibleSelectionState(visibleDownloads, selectedIds)

  const toggleSelectAllVisible = () => {
    setSelectedIds((current) => {
      const next = new Set(current)
      if (selectionState.allVisibleSelected) {
        for (const item of visibleDownloads) {
          next.delete(item.id)
        }
      } else {
        for (const item of visibleDownloads) {
          next.add(item.id)
        }
      }
      return next
    })
  }

  const toggleSelection = (downloadId: number) => {
    setSelectedIds((current) => {
      const next = new Set(current)
      if (next.has(downloadId)) {
        next.delete(downloadId)
      } else {
        next.add(downloadId)
      }
      return next
    })
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Downloads</h1>
          <p className="text-surface-400 mt-1">
            Manage your download queue and history
          </p>
        </div>
      </div>

      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard icon={<Activity className="w-5 h-5 text-primary-400" />} label="Active" value={stats.downloading + stats.importing} />
          <StatCard icon={<Clock className="w-5 h-5 text-yellow-400" />} label="Pending" value={stats.pending + stats.searching} />
          <StatCard icon={<CheckCircle className="w-5 h-5 text-green-400" />} label="Completed" value={stats.completed} />
          <StatCard icon={<AlertCircle className="w-5 h-5 text-red-400" />} label="Failed" value={stats.failed} />
        </div>
      )}

      <div className="flex items-center gap-1 border-b border-surface-800">
        {[{ id: 'queue' as Tab, label: 'Queue', icon: ArrowDownToLine }, { id: 'history' as Tab, label: 'History', icon: Clock }, { id: 'search' as Tab, label: 'Manual Search', icon: Search }].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              'flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors',
              activeTab === tab.id ? 'border-primary-500 text-primary-400' : 'border-transparent text-surface-400 hover:text-white'
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

      {(activeTab === 'queue' || activeTab === 'history') && selectionState.hasVisible && (
        <div className="card p-4 flex flex-wrap items-center gap-2">
          <button onClick={toggleSelectAllVisible} className="btn-ghost text-sm" disabled={deleteSelectedMutation.isPending || deleteAllMutation.isPending}>
            {selectionState.allVisibleSelected ? 'Unselect All' : 'Select All'}
          </button>
          <span className="text-sm text-surface-400">
            {selectionState.selectedVisibleCount} selected
          </span>
          <div className="ml-auto flex items-center gap-2">
            <button
              onClick={() => deleteSelectedMutation.mutate(Array.from(selectedIds))}
              disabled={!selectionState.hasSelection || deleteSelectedMutation.isPending || deleteAllMutation.isPending}
              className="btn-secondary text-sm"
            >
              <Trash2 className="w-4 h-4" />
              Delete Selected
            </button>
            <button
              onClick={() => deleteAllMutation.mutate(activeTab)}
              disabled={deleteAllMutation.isPending || deleteSelectedMutation.isPending}
              className="btn-ghost text-sm text-red-400 hover:text-red-300"
            >
              <Trash2 className="w-4 h-4" />
              Delete All
            </button>
          </div>
        </div>
      )}

      {activeTab === 'queue' && (
        <QueueTab downloads={queue} isLoading={queueLoading} onCancel={(id) => cancelMutation.mutate(id)} onRetry={(id) => retryMutation.mutate(id)} selectedIds={selectedIds} onToggleSelection={toggleSelection} />
      )}

      {activeTab === 'history' && (
        <HistoryTab downloads={history} isLoading={historyLoading} onRetry={(id) => retryMutation.mutate(id)} selectedIds={selectedIds} onToggleSelection={toggleSelection} />
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

function StatCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: number }) {
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

function QueueTab({ downloads, isLoading, onCancel, onRetry, selectedIds, onToggleSelection }: { downloads: DownloadType[]; isLoading: boolean; onCancel: (id: number) => void; onRetry: (id: number) => void; selectedIds: Set<number>; onToggleSelection: (id: number) => void }) {
  if (isLoading) return <LoadingPage message="Loading queue..." />

  if (downloads.length === 0) {
    return <EmptyState icon={<ArrowDownToLine className="w-8 h-8" />} title="Queue is empty" description="Add items from search or your wishlist to start downloading" />
  }

  return (
    <div className="space-y-3">
      {downloads.map((dl) => (
        <DownloadCard key={dl.id} download={dl} onCancel={() => onCancel(dl.id)} onRetry={() => onRetry(dl.id)} isSelected={selectedIds.has(dl.id)} onToggleSelection={() => onToggleSelection(dl.id)} />
      ))}
    </div>
  )
}

function HistoryTab({ downloads, isLoading, onRetry, selectedIds, onToggleSelection }: { downloads: DownloadType[]; isLoading: boolean; onRetry: (id: number) => void; selectedIds: Set<number>; onToggleSelection: (id: number) => void }) {
  if (isLoading) return <LoadingPage message="Loading history..." />

  if (downloads.length === 0) {
    return <EmptyState icon={<HardDrive className="w-8 h-8" />} title="No download history" description="Completed and failed downloads will appear here" />
  }

  return (
    <div className="space-y-3">
      {downloads.map((dl) => (
        <DownloadCard key={dl.id} download={dl} onRetry={dl.status === 'failed' ? () => onRetry(dl.id) : undefined} isSelected={selectedIds.has(dl.id)} onToggleSelection={() => onToggleSelection(dl.id)} />
      ))}
    </div>
  )
}

function DownloadCard({ download, onCancel, onRetry, isSelected, onToggleSelection }: { download: DownloadType; onCancel?: () => void; onRetry?: () => void; isSelected: boolean; onToggleSelection: () => void }) {
  const isActive = ['downloading', 'searching', 'queued', 'importing'].includes(download.status)
  const statusSummary = [
    download.download_client ? `Client: ${download.download_client}` : null,
    download.download_id ? `ID: ${download.download_id}` : null,
    download.download_path ? `Path: ${download.download_path}` : null,
  ].filter(Boolean).join(' · ')

  return (
    <div className="card p-4">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3 min-w-0 flex-1">
          <input type="checkbox" checked={isSelected} onChange={onToggleSelection} className="h-4 w-4 rounded border-surface-600 bg-surface-900 text-primary-500 focus:ring-primary-500" aria-label={`Select download ${download.id}`} />
          <div className="w-12 h-12 bg-surface-700 rounded flex-shrink-0 flex items-center justify-center text-surface-500">
            <Download className="w-5 h-5" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="font-medium text-white truncate">{download.album_title}</span>
              <StatusBadge status={download.status as any} />
            </div>
            <div className="flex items-center gap-2 text-sm text-surface-400 mt-0.5">
              <span className="truncate">{download.artist_name}</span>
              {download.release_quality && <><span>&middot;</span><span className="uppercase text-xs font-medium text-surface-300">{download.release_quality}</span></>}
              {download.release_size && <><span>&middot;</span><span>{formatBytes(download.release_size)}</span></>}
              {download.indexer_name && <><span>&middot;</span><span>{download.indexer_name}</span></>}
              {download.source !== 'manual' && <><span>&middot;</span><span className="capitalize">{download.source}</span></>}
            </div>
            {download.status_message && <p className="text-xs text-surface-500 mt-1">{download.status_message}</p>}
            {statusSummary && <p className="text-xs text-surface-500 mt-1 break-all">{statusSummary}</p>}
            <p className="text-[11px] text-surface-600 mt-1">
              Updated {new Date(download.updated_at || download.created_at).toLocaleString()}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3 flex-shrink-0">
          {download.status === 'downloading' && (
            <div className="text-right">
              <div className="text-sm font-medium text-white">{Math.round(download.progress)}%</div>
              {download.download_speed && download.download_speed > 0 && <div className="text-xs text-surface-400">{formatBytes(download.download_speed)}/s</div>}
              {download.eta_seconds && download.eta_seconds > 0 && <div className="text-xs text-surface-400">{formatEta(download.eta_seconds)}</div>}
            </div>
          )}

          {onCancel && isActive && (
            <button onClick={onCancel} className="btn-ghost p-2 text-red-400 hover:text-red-300" title="Cancel">
              <XCircle className="w-4 h-4" />
            </button>
          )}

          {onRetry && (
            <button onClick={onRetry} className="btn-ghost p-2 text-surface-400 hover:text-white" title="Retry">
              <RotateCcw className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {download.status === 'downloading' && download.progress > 0 && (
        <div className="mt-3 h-1.5 bg-surface-700 rounded-full overflow-hidden">
          <div className="h-full bg-primary-500 rounded-full transition-all duration-500" style={{ width: `${Math.min(download.progress, 100)}%` }} />
        </div>
      )}
    </div>
  )
}

function SearchTab({ artist, album, format, onArtistChange, onAlbumChange, onFormatChange, onSearch, onGrab, onAddToQueue, isSearching, isGrabbing, hasSearched, results }: { artist: string; album: string; format: string; onArtistChange: (v: string) => void; onAlbumChange: (v: string) => void; onFormatChange: (v: string) => void; onSearch: () => void; onGrab: (result: ReleaseSearchResult) => void; onAddToQueue: () => void; isSearching: boolean; isGrabbing: boolean; hasSearched: boolean; results: ReleaseSearchResult[] }) {
  return (
    <div className="space-y-6">
      <div className="card p-6">
        <h3 className="text-lg font-semibold text-white mb-4">Search Indexers</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-surface-300 mb-1">Artist</label>
            <input type="text" value={artist} onChange={(e) => onArtistChange(e.target.value)} placeholder="Artist name" className="input w-full" onKeyDown={(e) => e.key === 'Enter' && artist && album && onSearch()} />
          </div>
          <div>
            <label className="block text-sm font-medium text-surface-300 mb-1">Album</label>
            <input type="text" value={album} onChange={(e) => onAlbumChange(e.target.value)} placeholder="Album title" className="input w-full" onKeyDown={(e) => e.key === 'Enter' && artist && album && onSearch()} />
          </div>
          <div>
            <label className="block text-sm font-medium text-surface-300 mb-1">Preferred Format</label>
            <select value={format} onChange={(e) => onFormatChange(e.target.value)} className="input w-full">
              <option value="">Any</option>
              <option value="flac">FLAC</option>
              <option value="320">MP3 320</option>
              <option value="v0">MP3 V0</option>
            </select>
          </div>
        </div>
        <div className="flex items-center gap-3 mt-4">
          <button onClick={onSearch} disabled={!artist || !album || isSearching} className="btn-primary">
            {isSearching ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
            {isSearching ? 'Searching...' : 'Search Indexers'}
          </button>
          <button onClick={onAddToQueue} disabled={!artist || !album} className="btn-secondary">
            <ArrowDownToLine className="w-4 h-4" />
            Auto-Search & Queue
          </button>
        </div>
      </div>

      {results.length > 0 && (
        <div className="card">
          <div className="p-4 border-b border-surface-800">
            <h3 className="font-semibold text-white">{results.length} results found</h3>
          </div>
          <div className="divide-y divide-surface-800">
            {results.map((result, idx) => (
              <div key={`${result.guid}-${idx}`} className="p-4 flex items-center justify-between hover:bg-surface-800/50 transition-colors">
                <div className="min-w-0 flex-1">
                  <div className="font-medium text-white text-sm truncate">{result.title}</div>
                  <div className="flex items-center gap-3 mt-1 text-xs text-surface-400">
                    {result.indexer && <span>{result.indexer}</span>}
                    {result.quality && <span className="uppercase font-medium text-surface-300">{result.quality}</span>}
                    <span>{formatBytes(result.size)}</span>
                    <span>{result.seeders} seed{result.seeders !== 1 && 's'}</span>
                    <span className="text-surface-500">Score: {Math.round(result.score)}</span>
                  </div>
                </div>
                <button onClick={() => onGrab(result)} disabled={isGrabbing} className="btn-primary text-sm py-1.5 px-3 ml-4">
                  <Download className="w-3.5 h-3.5" />
                  Grab
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {hasSearched && results.length === 0 && (
        <EmptyState icon={<Search className="w-8 h-8" />} title="No results found" description="Try adjusting your search terms or format preference" />
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
