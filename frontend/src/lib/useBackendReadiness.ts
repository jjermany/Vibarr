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

  return {
    ...query,
    backendReady: query.data?.data?.status === 'ready',
  }
}

