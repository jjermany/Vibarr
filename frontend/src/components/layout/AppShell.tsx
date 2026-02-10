'use client'

import { useState } from 'react'
import { usePathname } from 'next/navigation'
import { Loader2, AlertCircle } from 'lucide-react'
import { Sidebar } from './Sidebar'
import { Header } from './Header'
import { useAuth } from '@/lib/auth'

const NO_SHELL_PATHS = ['/login', '/setup']

export function AppShell({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const pathname = usePathname()
  const { user, loading, setupStatus } = useAuth()

  // Login and setup pages render without the shell chrome
  if (NO_SHELL_PATHS.includes(pathname)) {
    return <>{children}</>
  }

  // Show a loading state while auth is bootstrapping
  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-surface-950">
        <Loader2 className="w-8 h-8 animate-spin text-primary-500" />
      </div>
    )
  }

  // Backend unreachable after retries - show connection error
  if (!setupStatus && !user) {
    return (
      <div className="flex h-screen items-center justify-center bg-surface-950 px-4">
        <div className="text-center max-w-md">
          <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
          <h2 className="text-lg font-semibold text-white mb-2">Unable to connect</h2>
          <p className="text-surface-400 text-sm mb-6">
            Could not reach the Vibarr backend. The server may still be starting up.
          </p>
          <button
            onClick={() => window.location.reload()}
            className="btn-primary px-6 py-2"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  // Not authenticated - the AuthProvider will redirect, just render nothing
  if (!user) {
    return null
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar
        mobileOpen={sidebarOpen}
        onMobileClose={() => setSidebarOpen(false)}
      />
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        <Header onMenuClick={() => setSidebarOpen(true)} />
        <main className="flex-1 overflow-y-auto p-4 sm:p-6">
          {children}
        </main>
      </div>
    </div>
  )
}
