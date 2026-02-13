'use client'

import { useQuery } from '@tanstack/react-query'
import { healthApi } from '@/lib/api'

export function useBackendReadiness() {
  const query = useQuery({
    queryKey: ['backend-readiness'],
    queryFn: () => healthApi.readiness(),
    retry: 3,
    refetchInterval: (q) => (q.state.data?.data?.status === 'ready' ? false : 3000),
    refetchOnWindowFocus: true,
  })

  const checks = query.data?.data?.checks

  return {
    ...query,
    backendReady: query.data?.data?.status === 'ready',
    databaseReady: checks?.database === true,
    checks,
  }
}

