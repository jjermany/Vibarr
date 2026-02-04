'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Search, RefreshCw, Bell } from 'lucide-react'
import { cn } from '@/lib/utils'

export function Header() {
  const [searchQuery, setSearchQuery] = useState('')
  const [isSearchFocused, setIsSearchFocused] = useState(false)
  const router = useRouter()

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (searchQuery.trim()) {
      router.push(`/search?q=${encodeURIComponent(searchQuery)}`)
    }
  }

  return (
    <header className="h-16 bg-surface-900/80 backdrop-blur-sm border-b border-surface-800 flex items-center justify-between px-6">
      {/* Search */}
      <form onSubmit={handleSearch} className="flex-1 max-w-xl">
        <div
          className={cn(
            'relative flex items-center transition-all',
            isSearchFocused && 'ring-2 ring-primary-500 rounded-lg'
          )}
        >
          <Search className="absolute left-3 w-5 h-5 text-surface-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onFocus={() => setIsSearchFocused(true)}
            onBlur={() => setIsSearchFocused(false)}
            placeholder="Search artists, albums, tracks..."
            className="w-full pl-10 pr-4 py-2.5 bg-surface-800 border border-surface-700 rounded-lg text-white placeholder-surface-400 focus:outline-none"
          />
        </div>
      </form>

      {/* Actions */}
      <div className="flex items-center gap-2 ml-4">
        <button
          className="btn-ghost p-2"
          title="Refresh library"
        >
          <RefreshCw className="w-5 h-5" />
        </button>
        <button
          className="btn-ghost p-2 relative"
          title="Notifications"
        >
          <Bell className="w-5 h-5" />
          <span className="absolute top-1 right-1 w-2 h-2 bg-accent-500 rounded-full" />
        </button>
      </div>
    </header>
  )
}
