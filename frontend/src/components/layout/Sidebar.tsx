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
]

export function Sidebar() {
  const pathname = usePathname()

  return (
    <aside className="w-64 bg-surface-900 border-r border-surface-800 flex flex-col">
      {/* Logo */}
      <div className="p-6">
        <Link href="/" className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-primary-500 to-accent-500 rounded-xl flex items-center justify-center">
            <Music2 className="w-6 h-6 text-white" />
          </div>
          <span className="text-xl font-bold text-white">Vibarr</span>
        </Link>
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
                  className={cn(
                    'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-primary-500/20 text-primary-400'
                      : 'text-surface-400 hover:text-white hover:bg-surface-800'
                  )}
                >
                  <item.icon className="w-5 h-5" />
                  {item.name}
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
          className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-surface-400 hover:text-white hover:bg-surface-800 transition-colors"
        >
          <Settings className="w-5 h-5" />
          Settings
        </Link>
      </div>
    </aside>
  )
}
