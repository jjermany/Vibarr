'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Music2, Loader2, AlertCircle, Shield, Check } from 'lucide-react'
import { authApi } from '@/lib/api'
import { useAuth } from '@/lib/auth'

export default function SetupPage() {
  const router = useRouter()
  const { login, user, loading: authLoading, setupStatus } = useAuth()

  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  // Redirect if setup already completed or user already logged in
  useEffect(() => {
    if (!authLoading) {
      if (user) {
        router.replace('/')
        return
      }
      if (setupStatus && !setupStatus.setup_required) {
        router.replace('/login')
      }
    }
  }, [authLoading, user, setupStatus, router])

  async function handleSetup(e: React.FormEvent) {
    e.preventDefault()
    setError('')

    if (password !== confirmPassword) {
      setError('Passwords do not match')
      return
    }

    if (password.length < 8) {
      setError('Password must be at least 8 characters')
      return
    }

    setLoading(true)

    try {
      const res = await authApi.setup({ username, email, password })
      login(res.data.access_token, res.data.user)
      router.replace('/')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to complete setup')
    } finally {
      setLoading(false)
    }
  }

  if (authLoading) {
    return (
      <div className="min-h-screen bg-surface-950 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary-500" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-surface-950 flex items-center justify-center px-4">
      <div className="w-full max-w-lg">
        {/* Logo & Welcome */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-primary-600/20 rounded-2xl mb-4">
            <Music2 className="w-8 h-8 text-primary-400" />
          </div>
          <h1 className="text-2xl font-bold text-white">Welcome to Vibarr</h1>
          <p className="text-surface-400 mt-1">
            Create your admin account to get started
          </p>
        </div>

        {/* Setup form */}
        <div className="card p-6">
          <div className="flex items-center gap-3 mb-6 p-3 bg-primary-500/10 border border-primary-500/20 rounded-lg">
            <Shield className="w-5 h-5 text-primary-400 flex-shrink-0" />
            <div className="text-sm">
              <div className="font-medium text-primary-300">Admin Account</div>
              <div className="text-primary-400/70">
                This account will have full administrator access to Vibarr.
              </div>
            </div>
          </div>

          <form onSubmit={handleSetup} className="space-y-4">
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
                placeholder="Choose a username"
                required
                autoFocus
                className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-surface-500 focus:outline-none focus:border-primary-500"
              />
            </div>

            <div className="space-y-1.5">
              <label className="block text-sm font-medium text-white">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="admin@example.com"
                required
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
                placeholder="At least 8 characters"
                required
                minLength={8}
                className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-surface-500 focus:outline-none focus:border-primary-500"
              />
            </div>

            <div className="space-y-1.5">
              <label className="block text-sm font-medium text-white">
                Confirm Password
              </label>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Re-enter your password"
                required
                className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-surface-500 focus:outline-none focus:border-primary-500"
              />
              {confirmPassword && password !== confirmPassword && (
                <p className="text-xs text-red-400">Passwords do not match</p>
              )}
              {confirmPassword && password === confirmPassword && (
                <p className="text-xs text-green-400 flex items-center gap-1">
                  <Check className="w-3 h-3" /> Passwords match
                </p>
              )}
            </div>

            <button
              type="submit"
              disabled={loading || !username || !email || !password || password !== confirmPassword}
              className="w-full btn-primary py-2.5 mt-2"
            >
              {loading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Shield className="w-4 h-4" />
              )}
              Create Admin Account
            </button>
          </form>
        </div>

        <p className="text-xs text-surface-500 text-center mt-4">
          After setup, you can enable Plex authentication in Settings to allow
          additional users to sign in with their Plex accounts.
        </p>
      </div>
    </div>
  )
}
