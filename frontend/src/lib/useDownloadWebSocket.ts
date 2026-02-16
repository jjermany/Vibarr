'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import type { Download } from '@/lib/api'

interface DownloadUpdateMessage {
  type: 'download_update'
  download: Partial<Download> & { id: number }
}

interface StatsUpdateMessage {
  type: 'stats_update'
  stats: Record<string, number>
}

type WsMessage = DownloadUpdateMessage | StatsUpdateMessage

const WS_RECONNECT_BASE_MS = 3000
const WS_RECONNECT_MAX_MS = 30000

export function useDownloadWebSocket(): { isConnected: boolean } {
  const queryClient = useQueryClient()
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reconnectDelayRef = useRef(WS_RECONNECT_BASE_MS)
  const [isConnected, setIsConnected] = useState(false)

  const getToken = useCallback((): string | null => {
    if (typeof window === 'undefined') return null
    return localStorage.getItem('vibarr_token')
  }, [])

  const handleMessage = useCallback(
    (event: MessageEvent) => {
      try {
        const msg: WsMessage = JSON.parse(event.data as string)

        if (msg.type === 'download_update') {
          const { download } = msg

          queryClient.setQueryData<Download[]>(['download-queue'], (old) => {
            if (!old) return old
            return old.map((d) => (d.id === download.id ? { ...d, ...download } : d))
          })

          queryClient.setQueryData<Download[]>(['download-history'], (old) => {
            if (!old) return old
            return old.map((d) => (d.id === download.id ? { ...d, ...download } : d))
          })

          if (
            download.status === 'completed' ||
            download.status === 'failed' ||
            download.status === 'cancelled'
          ) {
            queryClient.invalidateQueries({ queryKey: ['download-stats'] })
          }
        }

        if (msg.type === 'stats_update') {
          queryClient.setQueryData(['download-stats'], msg.stats)
        }
      } catch {
        // Ignore malformed messages
      }
    },
    [queryClient]
  )

  const connect = useCallback(() => {
    const token = getToken()
    if (!token || typeof window === 'undefined') return

    const apiBase = process.env.NEXT_PUBLIC_API_URL
      ? new URL(process.env.NEXT_PUBLIC_API_URL).host
      : window.location.host
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const url = `${protocol}://${apiBase}/ws/downloads?token=${encodeURIComponent(token)}`

    try {
      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => {
        setIsConnected(true)
        reconnectDelayRef.current = WS_RECONNECT_BASE_MS
      }

      ws.onmessage = handleMessage

      ws.onclose = () => {
        setIsConnected(false)
        wsRef.current = null
        reconnectTimerRef.current = setTimeout(() => {
          reconnectDelayRef.current = Math.min(
            reconnectDelayRef.current * 2,
            WS_RECONNECT_MAX_MS
          )
          connect()
        }, reconnectDelayRef.current)
      }

      ws.onerror = () => {
        ws.close()
      }
    } catch {
      // WebSocket not supported or URL invalid — fall back to polling silently
    }
  }, [getToken, handleMessage])

  useEffect(() => {
    connect()

    return () => {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current)
      }
      if (wsRef.current) {
        // Prevent onclose from triggering a reconnect on intentional cleanup
        wsRef.current.onclose = null
        wsRef.current.close()
      }
    }
  }, [connect])

  return { isConnected }
}
