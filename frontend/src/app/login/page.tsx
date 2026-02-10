'use client'

import { useState, useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { LogIn, Loader2, Music2, AlertCircle } from 'lucide-react'
import { authApi } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { cn } from '@/lib/utils'

export default function LoginPage() {
  const router = useRouter()
  const { login, user, loading: authLoading, setupStatus } = useAuth()

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  // Plex OAuth state
  const [plexLoading, setPlexLoading] = useState(false)
  const [plexError, setPlexError] = useState('')
  const plexPollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Redirect if already logged in
  useEffect(() => {
    if (!authLoading && user) {
      router.replace('/')
    }
  }, [authLoading, user, router])

  // Cleanup Plex polling on unmount
  useEffect(() => {
    return () => {
      if (plexPollRef.current) clearInterval(plexPollRef.current)
    }
  }, [])

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const res = await authApi.login({ username, password })
      login(res.data.access_token, res.data.user)
      router.replace('/')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Invalid username or password')
    } finally {
      setLoading(false)
    }
  }

  async function handlePlexLogin() {
    setPlexError('')
    setPlexLoading(true)

    try {
      // Get a client ID or generate one
      let clientId = localStorage.getItem('vibarr_plex_client_id')
      if (!clientId) {
        clientId = crypto.randomUUID()
        localStorage.setItem('vibarr_plex_client_id', clientId)
      }

      // Create PIN
      const pinRes = await authApi.createPlexPin(clientId)
      const { id: pinId, auth_url } = pinRes.data

      // Open Plex auth in a new window
      const authWindow = window.open(auth_url, 'plex_auth', 'width=800,height=600')

      // Poll for PIN completion
      plexPollRef.current = setInterval(async () => {
        try {
          const callbackRes = await authApi.plexCallback(pinId, clientId!)
          // Success - stop polling
          if (plexPollRef.current) clearInterval(plexPollRef.current)
          plexPollRef.current = null
          setPlexLoading(false)

          if (authWindow && !authWindow.closed) authWindow.close()

          login(callbackRes.data.access_token, callbackRes.data.user)
          router.replace('/')
        } catch (err: any) {
          // 401 means PIN not yet claimed - keep polling
          if (err.response?.status === 401) return
          // 403 means access denied - stop polling
          if (plexPollRef.current) clearInterval(plexPollRef.current)
          plexPollRef.current = null
          setPlexLoading(false)
          if (authWindow && !authWindow.closed) authWindow.close()
          setPlexError(err.response?.data?.detail || 'Plex authentication failed')
        }
      }, 2000)

      // Stop polling after 5 minutes
      setTimeout(() => {
        if (plexPollRef.current) {
          clearInterval(plexPollRef.current)
          plexPollRef.current = null
          setPlexLoading(false)
          setPlexError('Plex authentication timed out')
        }
      }, 300000)
    } catch (err: any) {
      setPlexLoading(false)
      setPlexError(err.response?.data?.detail || 'Failed to start Plex authentication')
    }
  }

  if (authLoading) {
    return (
      <div className="min-h-screen bg-surface-950 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary-500" />
      </div>
    )
  }

  const showPlexLogin = setupStatus?.plex_auth_enabled

  return (
    <div className="min-h-screen bg-surface-950 flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-primary-600/20 rounded-2xl mb-4">
            <Music2 className="w-8 h-8 text-primary-400" />
          </div>
          <h1 className="text-2xl font-bold text-white">Vibarr</h1>
          <p className="text-surface-400 mt-1">Sign in to continue</p>
        </div>

        {/* Login form */}
        <div className="card p-6">
          <form onSubmit={handleLogin} className="space-y-4">
            {error && (
              <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-sm text-red-400">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                {error}
              </div>
            )}

            <div className="space-y-1.5">
              <label className="block text-sm font-medium text-white">
                Username
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter your username"
                required
                autoFocus
                className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-surface-500 focus:outline-none focus:border-primary-500"
              />
            </div>

            <div className="space-y-1.5">
              <label className="block text-sm font-medium text-white">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                required
                className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-surface-500 focus:outline-none focus:border-primary-500"
              />
            </div>

            <button
              type="submit"
              disabled={loading || !username || !password}
              className="w-full btn-primary py-2.5"
            >
              {loading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <LogIn className="w-4 h-4" />
              )}
              Sign In
            </button>
          </form>

          {/* Plex login */}
          {showPlexLogin && (
            <>
              <div className="relative my-6">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-surface-700" />
                </div>
                <div className="relative flex justify-center text-sm">
                  <span className="bg-surface-900 px-3 text-surface-400">
                    or
                  </span>
                </div>
              </div>

              {plexError && (
                <div className="flex items-center gap-2 p-3 mb-4 bg-red-500/10 border border-red-500/30 rounded-lg text-sm text-red-400">
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />
                  {plexError}
                </div>
              )}

              <button
                onClick={handlePlexLogin}
                disabled={plexLoading}
                className={cn(
                  'w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg font-medium transition-colors',
                  'bg-[#e5a00d]/10 text-[#e5a00d] border border-[#e5a00d]/30',
                  'hover:bg-[#e5a00d]/20 disabled:opacity-50 disabled:cursor-not-allowed'
                )}
              >
                {plexLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Waiting for Plex...
                  </>
                ) : (
                  <>
                    <svg viewBox="0 0 24 24" className="w-5 h-5 fill-current">
                      <path d="M11.643 0H4.68l7.679 12L4.68 24h6.963l7.677-12z" />
                    </svg>
                    Sign in with Plex
                  </>
                )}
              </button>

              <p className="text-xs text-surface-500 mt-3 text-center">
                Plex users with shared access to the music library can sign in
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
