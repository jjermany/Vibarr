'use client'

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from 'react'
import { useRouter, usePathname } from 'next/navigation'
import { authApi, type AppUser, type SetupStatus } from '@/lib/api'

interface AuthContextValue {
  user: AppUser | null
  token: string | null
  loading: boolean
  setupStatus: SetupStatus | null
  login: (token: string, user: AppUser) => void
  logout: () => void
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  token: null,
  loading: true,
  setupStatus: null,
  login: () => {},
  logout: () => {},
})

export function useAuth() {
  return useContext(AuthContext)
}

const PUBLIC_PATHS = ['/login', '/setup']

/** Retry fetching setup status with exponential backoff for when the backend isn't ready yet. */
async function fetchSetupStatusWithRetry(maxRetries = 5): Promise<SetupStatus> {
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const res = await authApi.getSetupStatus()
      return res.data
    } catch {
      if (attempt === maxRetries) throw new Error('Backend unavailable')
      // Exponential backoff: 1s, 2s, 4s, 8s, 16s
      await new Promise((r) => setTimeout(r, 1000 * Math.pow(2, attempt)))
    }
  }
  throw new Error('Backend unavailable')
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter()
  const pathname = usePathname()
  const [user, setUser] = useState<AppUser | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [setupStatus, setSetupStatus] = useState<SetupStatus | null>(null)

  const login = useCallback((newToken: string, newUser: AppUser) => {
    localStorage.setItem('vibarr_token', newToken)
    localStorage.setItem('vibarr_user', JSON.stringify(newUser))
    setToken(newToken)
    setUser(newUser)
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('vibarr_token')
    localStorage.removeItem('vibarr_user')
    setToken(null)
    setUser(null)
    router.push('/login')
  }, [router])

  // Bootstrap: check setup status and restore session
  useEffect(() => {
    let cancelled = false

    async function bootstrap() {
      try {
        // Always check setup status first (this endpoint is unauthenticated)
        // Retry with backoff in case the backend isn't ready yet (e.g. fresh container start)
        const status = await fetchSetupStatusWithRetry()
        if (cancelled) return
        setSetupStatus(status)

        // If setup is required, redirect to setup page
        if (status.setup_required) {
          setLoading(false)
          if (pathname !== '/setup') {
            router.replace('/setup')
          }
          return
        }

        // Try to restore session from localStorage
        const savedToken = localStorage.getItem('vibarr_token')
        const savedUser = localStorage.getItem('vibarr_user')

        if (savedToken && savedUser) {
          setToken(savedToken)
          setUser(JSON.parse(savedUser))

          // Validate token by fetching profile
          try {
            const profileRes = await authApi.getProfile()
            if (!cancelled) {
              setUser(profileRes.data)
              localStorage.setItem('vibarr_user', JSON.stringify(profileRes.data))
            }
          } catch {
            // Token invalid, clear and redirect
            if (!cancelled) {
              localStorage.removeItem('vibarr_token')
              localStorage.removeItem('vibarr_user')
              setToken(null)
              setUser(null)
              if (!PUBLIC_PATHS.includes(pathname)) {
                router.replace('/login')
              }
            }
          }
        } else if (!PUBLIC_PATHS.includes(pathname)) {
          // No saved session and not on a public page
          router.replace('/login')
        }
      } catch {
        // Backend still unavailable after retries - stay on loading screen
        // so we don't incorrectly redirect to login on a fresh install
        return
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    bootstrap()
    return () => { cancelled = true }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Guard routes after initial load
  useEffect(() => {
    if (loading) return

    if (setupStatus?.setup_required && pathname !== '/setup') {
      router.replace('/setup')
      return
    }

    // Only redirect to login when we have confirmed setup is complete
    if (setupStatus && !setupStatus.setup_required && !user && !PUBLIC_PATHS.includes(pathname)) {
      router.replace('/login')
    }
  }, [pathname, user, loading, setupStatus, router])

  return (
    <AuthContext.Provider value={{ user, token, loading, setupStatus, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}
