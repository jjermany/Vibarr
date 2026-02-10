'use client'

import { useState, useEffect } from 'react'
import {
  Folder,
  File,
  ChevronRight,
  ArrowUp,
  X,
  Loader2,
  FolderOpen,
  Check,
} from 'lucide-react'
import { settingsApi, type BrowseEntry } from '@/lib/api'
import { cn } from '@/lib/utils'

interface PathBrowserModalProps {
  isOpen: boolean
  onClose: () => void
  onSelect: (path: string) => void
  initialPath?: string
  /** When true, only directories can be selected. Default true. */
  dirOnly?: boolean
  title?: string
}

export function PathBrowserModal({
  isOpen,
  onClose,
  onSelect,
  initialPath = '/',
  dirOnly = true,
  title = 'Browse Path',
}: PathBrowserModalProps) {
  const [currentPath, setCurrentPath] = useState(initialPath || '/')
  const [entries, setEntries] = useState<BrowseEntry[]>([])
  const [parentPath, setParentPath] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedPath, setSelectedPath] = useState<string | null>(null)

  useEffect(() => {
    if (isOpen) {
      // Determine starting path: use initialPath's parent if it's a file path
      const startPath = initialPath && initialPath !== '/' ? initialPath : '/'
      browse(startPath)
    }
  }, [isOpen, initialPath])

  const browse = async (path: string) => {
    setLoading(true)
    setError(null)
    try {
      const res = await settingsApi.browse(path)
      const data = res.data
      setCurrentPath(data.current_path)
      setParentPath(data.parent)
      setEntries(data.entries)
      setSelectedPath(null)
    } catch (err: any) {
      const detail = err.response?.data?.detail || 'Failed to browse path'
      setError(detail)
      // If path doesn't exist, try parent
      if (err.response?.status === 404 && path !== '/') {
        const parent = path.split('/').slice(0, -1).join('/') || '/'
        browse(parent)
        return
      }
    } finally {
      setLoading(false)
    }
  }

  const handleEntryClick = (entry: BrowseEntry) => {
    if (entry.is_dir) {
      browse(entry.path)
    } else if (!dirOnly) {
      setSelectedPath(entry.path)
    }
  }

  const handleSelect = () => {
    const path = selectedPath || currentPath
    onSelect(path)
    onClose()
  }

  const handleSelectEntry = (entry: BrowseEntry) => {
    if (entry.is_dir) {
      setSelectedPath(entry.path)
    } else if (!dirOnly) {
      setSelectedPath(entry.path)
    }
  }

  const formatSize = (bytes: number | null) => {
    if (bytes === null) return ''
    if (bytes === 0) return '0 B'
    const units = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(1024))
    return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`
  }

  if (!isOpen) return null

  const dirs = entries.filter((e) => e.is_dir)
  const files = dirOnly ? [] : entries.filter((e) => !e.is_dir)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Overlay */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative bg-surface-900 border border-surface-700 rounded-xl shadow-2xl w-full max-w-lg mx-4 max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-surface-700">
          <h3 className="text-lg font-semibold text-white">{title}</h3>
          <button
            onClick={onClose}
            className="p-1 text-surface-400 hover:text-white rounded-lg hover:bg-surface-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Current path breadcrumb */}
        <div className="px-4 py-2 border-b border-surface-800 flex items-center gap-2">
          {parentPath && (
            <button
              onClick={() => browse(parentPath)}
              className="p-1 text-surface-400 hover:text-white rounded hover:bg-surface-800 transition-colors flex-shrink-0"
              title="Go up"
            >
              <ArrowUp className="w-4 h-4" />
            </button>
          )}
          <div className="flex items-center gap-1 text-sm text-surface-300 overflow-x-auto whitespace-nowrap">
            <FolderOpen className="w-4 h-4 text-primary-400 flex-shrink-0" />
            <span className="font-mono text-xs">{currentPath}</span>
          </div>
        </div>

        {/* Entries list */}
        <div className="flex-1 overflow-y-auto min-h-[200px] max-h-[400px]">
          {loading ? (
            <div className="flex items-center justify-center py-12 text-surface-400">
              <Loader2 className="w-5 h-5 animate-spin mr-2" />
              Loading...
            </div>
          ) : error ? (
            <div className="p-4 text-sm text-red-400">{error}</div>
          ) : dirs.length === 0 && files.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-surface-500">
              <Folder className="w-8 h-8 mb-2" />
              <span className="text-sm">Empty directory</span>
            </div>
          ) : (
            <div className="py-1">
              {dirs.map((entry) => (
                <button
                  key={entry.path}
                  className={cn(
                    'w-full flex items-center gap-3 px-4 py-2 text-left hover:bg-surface-800 transition-colors group',
                    selectedPath === entry.path &&
                      'bg-primary-500/10 border-l-2 border-primary-500'
                  )}
                  onClick={() => handleSelectEntry(entry)}
                  onDoubleClick={() => handleEntryClick(entry)}
                >
                  <Folder className="w-4 h-4 text-primary-400 flex-shrink-0" />
                  <span className="text-sm text-white truncate flex-1">
                    {entry.name}
                  </span>
                  <ChevronRight className="w-4 h-4 text-surface-600 group-hover:text-surface-400 flex-shrink-0" />
                </button>
              ))}
              {files.map((entry) => (
                <button
                  key={entry.path}
                  className={cn(
                    'w-full flex items-center gap-3 px-4 py-2 text-left hover:bg-surface-800 transition-colors',
                    selectedPath === entry.path &&
                      'bg-primary-500/10 border-l-2 border-primary-500'
                  )}
                  onClick={() => handleSelectEntry(entry)}
                  onDoubleClick={() => {
                    onSelect(entry.path)
                    onClose()
                  }}
                >
                  <File className="w-4 h-4 text-surface-500 flex-shrink-0" />
                  <span className="text-sm text-surface-300 truncate flex-1">
                    {entry.name}
                  </span>
                  {entry.size !== null && (
                    <span className="text-xs text-surface-500 flex-shrink-0">
                      {formatSize(entry.size)}
                    </span>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-surface-700 p-4 flex items-center justify-between gap-3">
          <div className="text-xs text-surface-400 truncate flex-1">
            {selectedPath ? (
              <span className="font-mono">{selectedPath}</span>
            ) : (
              <span>
                {dirOnly
                  ? 'Click to select, double-click to open'
                  : 'Select a file or directory'}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <button
              onClick={onClose}
              className="btn-ghost text-sm px-3 py-1.5"
            >
              Cancel
            </button>
            <button
              onClick={handleSelect}
              className="btn-primary text-sm px-3 py-1.5 flex items-center gap-1.5"
            >
              <Check className="w-3.5 h-3.5" />
              Select {dirOnly ? 'Directory' : 'Path'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
