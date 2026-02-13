'use client'

import { useQuery } from '@tanstack/react-query'
import { healthApi } from '@/lib/api'

export function isApiUsable(status?: string, checks?: { database?: boolean }) {
  return checks?.database === true || status === 'ready'
}

export function useBackendReadiness() {
  const query = useQuery({
    queryKey: ['backend-readiness'],
    queryFn: () => healthApi.readiness(),
    retry: 3,
    refetchInterval: (q) => (q.state.data?.data?.status === 'ready' ? false : 3000),
    refetchOnWindowFocus: true,
  })

  const checks = query.data?.data?.checks
  const status = query.data?.data?.status

  return {
    ...query,
    backendReady: status === 'ready',
    databaseReady: checks?.database === true,
    apiUsable: isApiUsable(status, checks),
    checks,
  }
}
