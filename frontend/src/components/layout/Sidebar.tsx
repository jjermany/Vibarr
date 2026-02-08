'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  Home,
  Search,
  Library,
  Compass,
  Heart,
  Download,
  BarChart3,
  Settings,
  Music2,
  X,
  Users,
  Zap,
  User,
} from 'lucide-react'
import { cn } from '@/lib/utils'

const navigation = [
  { name: 'Home', href: '/', icon: Home },
  { name: 'Search', href: '/search', icon: Search },
  { name: 'Explore', href: '/explore', icon: Compass },
  { name: 'Library', href: '/library', icon: Library },
  { name: 'Wishlist', href: '/wishlist', icon: Heart },
  { name: 'Downloads', href: '/downloads', icon: Download },
  { name: 'Stats', href: '/stats', icon: BarChart3 },
  { name: 'Social', href: '/social', icon: Users },
  { name: 'Automation', href: '/automation', icon: Zap },
  { name: 'Profile', href: '/profile', icon: User },
]

export function Sidebar({
  mobileOpen = false,
  onMobileClose,
}: {
  mobileOpen?: boolean
  onMobileClose?: () => void
}) {
  const pathname = usePathname()

  return (
    <>
      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm lg:hidden"
          onClick={onMobileClose}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-50 w-64 bg-surface-900 border-r border-surface-800 flex flex-col transition-transform duration-300 lg:static lg:translate-x-0',
          mobileOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        {/* Logo */}
        <div className="p-6 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-3" onClick={onMobileClose}>
            <div className="w-10 h-10 bg-gradient-to-br from-primary-500 to-accent-500 rounded-xl flex items-center justify-center shadow-lg shadow-primary-500/20">
              <Music2 className="w-6 h-6 text-white" />
            </div>
            <span className="text-xl font-bold text-white tracking-tight">Vibarr</span>
          </Link>
          <button
            onClick={onMobileClose}
            className="lg:hidden p-1 rounded-md text-surface-400 hover:text-white hover:bg-surface-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3">
          <ul className="space-y-1">
            {navigation.map((item) => {
              const isActive = pathname === item.href
              return (
                <li key={item.name}>
                  <Link
                    href={item.href}
                    onClick={onMobileClose}
                    className={cn(
                      'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all',
                      isActive
                        ? 'bg-primary-500/20 text-primary-400 shadow-sm'
                        : 'text-surface-400 hover:text-white hover:bg-surface-800'
                    )}
                  >
                    <item.icon className={cn('w-5 h-5', isActive && 'drop-shadow-sm')} />
                    {item.name}
                    {isActive && (
                      <div className="ml-auto w-1.5 h-1.5 rounded-full bg-primary-400" />
                    )}
                  </Link>
                </li>
              )
            })}
          </ul>
        </nav>

        {/* Settings */}
        <div className="p-3 border-t border-surface-800">
          <Link
            href="/settings"
            onClick={onMobileClose}
            className={cn(
              'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
              pathname === '/settings'
                ? 'bg-primary-500/20 text-primary-400'
                : 'text-surface-400 hover:text-white hover:bg-surface-800'
            )}
          >
            <Settings className="w-5 h-5" />
            Settings
          </Link>
        </div>
      </aside>
    </>
  )
}
