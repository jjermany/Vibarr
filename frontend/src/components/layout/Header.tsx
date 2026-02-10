'use client'

import { useState, useRef, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import {
  Search,
  RefreshCw,
  Bell,
  Menu,
  LogOut,
  User,
  ChevronDown,
  CheckCircle,
  XCircle,
  Loader2,
  Info,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAuth } from '@/lib/auth'
import { settingsApi, type Notification } from '@/lib/api'

function timeAgo(timestamp: string | null): string {
  if (!timestamp) return ''
  const seconds = Math.floor(
    (Date.now() - new Date(timestamp).getTime()) / 1000
  )
  if (seconds < 60) return 'just now'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

export function Header({ onMenuClick }: { onMenuClick?: () => void }) {
  const [searchQuery, setSearchQuery] = useState('')
  const [isSearchFocused, setIsSearchFocused] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const [notifOpen, setNotifOpen] = useState(false)
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [notifLoading, setNotifLoading] = useState(false)
  const [hasUnread, setHasUnread] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)
  const notifRef = useRef<HTMLDivElement>(null)
  const router = useRouter()
  const { user, logout } = useAuth()

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (searchQuery.trim()) {
      router.push(`/search?q=${encodeURIComponent(searchQuery)}`)
    }
  }

  // Close menus when clicking outside
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false)
      }
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) {
        setNotifOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const fetchNotifications = async () => {
    setNotifLoading(true)
    try {
      const res = await settingsApi.getNotifications(15)
      setNotifications(res.data.notifications)
      setHasUnread(false)
    } catch {
      // Silently fail - user may not be admin
    } finally {
      setNotifLoading(false)
    }
  }

  const handleNotifToggle = () => {
    const opening = !notifOpen
    setNotifOpen(opening)
    if (opening) {
      fetchNotifications()
    }
  }

  // Poll for new activity to show the badge
  useEffect(() => {
    if (!user?.is_admin) return
    let lastCheck = ''
    const checkForNew = async () => {
      try {
        const res = await settingsApi.getNotifications(1)
        const latest = res.data.notifications[0]
        if (latest && latest.timestamp && latest.timestamp !== lastCheck) {
          if (lastCheck) setHasUnread(true)
          lastCheck = latest.timestamp
        }
      } catch {
        // ignore
      }
    }
    checkForNew()
    const interval = setInterval(checkForNew, 60000)
    return () => clearInterval(interval)
  }, [user?.is_admin])

  const notifIcon = (type: string) => {
    switch (type) {
      case 'success':
        return <CheckCircle className="w-4 h-4 text-green-400 flex-shrink-0" />
      case 'error':
        return <XCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
      default:
        return <Info className="w-4 h-4 text-primary-400 flex-shrink-0" />
    }
  }

  return (
    <header className="h-16 bg-surface-900/80 backdrop-blur-sm border-b border-surface-800 flex items-center justify-between px-4 sm:px-6">
      {/* Mobile menu button */}
      <button
        onClick={onMenuClick}
        className="lg:hidden p-2 mr-2 rounded-lg text-surface-400 hover:text-white hover:bg-surface-800 transition-colors"
      >
        <Menu className="w-5 h-5" />
      </button>

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
            className="w-full pl-10 pr-4 py-2.5 bg-surface-800 border border-surface-700 rounded-lg text-white placeholder-surface-400 focus:outline-none text-sm sm:text-base"
          />
        </div>
      </form>

      {/* Actions */}
      <div className="flex items-center gap-1 sm:gap-2 ml-2 sm:ml-4">
        <button
          className="btn-ghost p-2"
          title="Refresh library"
        >
          <RefreshCw className="w-5 h-5" />
        </button>

        {/* Notifications */}
        <div className="relative" ref={notifRef}>
          <button
            className="btn-ghost p-2 relative"
            title="Notifications"
            onClick={handleNotifToggle}
          >
            <Bell className="w-5 h-5" />
            {hasUnread && (
              <span className="absolute top-1 right-1 w-2 h-2 bg-accent-500 rounded-full" />
            )}
          </button>

          {notifOpen && (
            <div className="absolute right-0 top-full mt-1 w-80 bg-surface-800 border border-surface-700 rounded-lg shadow-xl z-50 overflow-hidden">
              <div className="px-4 py-3 border-b border-surface-700 flex items-center justify-between">
                <h4 className="text-sm font-semibold text-white">
                  Notifications
                </h4>
                <button
                  onClick={fetchNotifications}
                  className="text-xs text-surface-400 hover:text-white transition-colors"
                >
                  Refresh
                </button>
              </div>

              <div className="max-h-80 overflow-y-auto">
                {notifLoading ? (
                  <div className="flex items-center justify-center py-8 text-surface-400">
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                    <span className="text-sm">Loading...</span>
                  </div>
                ) : notifications.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-8 text-surface-500">
                    <Bell className="w-6 h-6 mb-2" />
                    <span className="text-sm">No notifications yet</span>
                  </div>
                ) : (
                  notifications.map((n) => (
                    <div
                      key={`${n.id}-${n.status}`}
                      className="px-4 py-3 border-b border-surface-700/50 hover:bg-surface-700/30 transition-colors"
                    >
                      <div className="flex items-start gap-3">
                        {notifIcon(n.type)}
                        <div className="flex-1 min-w-0">
                          <p className="text-sm text-white leading-snug truncate">
                            {n.message}
                          </p>
                          <p className="text-xs text-surface-500 mt-0.5">
                            {timeAgo(n.timestamp)}
                          </p>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>

              {notifications.length > 0 && (
                <div className="px-4 py-2 border-t border-surface-700">
                  <button
                    onClick={() => {
                      setNotifOpen(false)
                      router.push('/downloads')
                    }}
                    className="text-xs text-primary-400 hover:text-primary-300 transition-colors"
                  >
                    View all downloads
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* User menu */}
        {user && (
          <div className="relative" ref={menuRef}>
            <button
              onClick={() => setMenuOpen(!menuOpen)}
              className="flex items-center gap-2 px-2 py-1.5 rounded-lg text-surface-300 hover:text-white hover:bg-surface-800 transition-colors"
            >
              {user.avatar_url ? (
                <img
                  src={user.avatar_url}
                  alt=""
                  className="w-7 h-7 rounded-full object-cover"
                />
              ) : (
                <div className="w-7 h-7 rounded-full bg-primary-600/30 flex items-center justify-center">
                  <User className="w-4 h-4 text-primary-400" />
                </div>
              )}
              <span className="hidden sm:block text-sm font-medium max-w-[100px] truncate">
                {user.display_name || user.username}
              </span>
              <ChevronDown className="w-3.5 h-3.5 hidden sm:block" />
            </button>

            {menuOpen && (
              <div className="absolute right-0 top-full mt-1 w-48 bg-surface-800 border border-surface-700 rounded-lg shadow-xl z-50 py-1">
                <div className="px-3 py-2 border-b border-surface-700">
                  <div className="text-sm font-medium text-white truncate">
                    {user.display_name || user.username}
                  </div>
                  <div className="text-xs text-surface-400 truncate">
                    {user.email}
                  </div>
                  {user.is_admin && (
                    <span className="inline-block mt-1 text-[10px] px-1.5 py-0.5 rounded bg-primary-500/20 text-primary-400 font-medium">
                      Admin
                    </span>
                  )}
                </div>
                <button
                  onClick={() => {
                    setMenuOpen(false)
                    router.push('/profile')
                  }}
                  className="w-full text-left px-3 py-2 text-sm text-surface-300 hover:text-white hover:bg-surface-700 transition-colors flex items-center gap-2"
                >
                  <User className="w-4 h-4" />
                  Profile
                </button>
                <button
                  onClick={() => {
                    setMenuOpen(false)
                    logout()
                  }}
                  className="w-full text-left px-3 py-2 text-sm text-red-400 hover:text-red-300 hover:bg-surface-700 transition-colors flex items-center gap-2"
                >
                  <LogOut className="w-4 h-4" />
                  Sign Out
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </header>
  )
}
