'use client'

import { cn } from '@/lib/utils'
import type { Status } from '@/lib/status'
import {
  Clock,
  Search,
  CheckCircle,
  Download,
  AlertCircle,
  XCircle,
  Loader2,
} from 'lucide-react'

interface StatusBadgeProps {
  status: Status
  showIcon?: boolean
}

const statusConfig: Record<
  Status,
  { label: string; className: string; icon: React.ComponentType<any> }
> = {
  wanted: {
    label: 'Wanted',
    className: 'bg-blue-500/20 text-blue-400',
    icon: Clock,
  },
  pending: {
    label: 'Pending',
    className: 'bg-surface-700 text-surface-300',
    icon: Clock,
  },
  searching: {
    label: 'Searching',
    className: 'bg-yellow-500/20 text-yellow-400',
    icon: Search,
  },
  found: {
    label: 'Found',
    className: 'bg-green-500/20 text-green-400',
    icon: CheckCircle,
  },
  queued: {
    label: 'Queued',
    className: 'bg-purple-500/20 text-purple-400',
    icon: Clock,
  },
  downloading: {
    label: 'Downloading',
    className: 'bg-primary-500/20 text-primary-400',
    icon: Loader2,
  },
  importing: {
    label: 'Importing',
    className: 'bg-cyan-500/20 text-cyan-400',
    icon: Loader2,
  },
  downloaded: {
    label: 'Downloaded',
    className: 'bg-green-500/20 text-green-400',
    icon: CheckCircle,
  },
  completed: {
    label: 'Completed',
    className: 'bg-green-500/20 text-green-400',
    icon: CheckCircle,
  },
  failed: {
    label: 'Failed',
    className: 'bg-red-500/20 text-red-400',
    icon: XCircle,
  },
  cancelled: {
    label: 'Cancelled',
    className: 'bg-surface-700 text-surface-400',
    icon: XCircle,
  },
}

export function StatusBadge({ status, showIcon = true }: StatusBadgeProps) {
  const config = statusConfig[status]
  const Icon = config.icon
  const isAnimated = status === 'downloading' || status === 'importing' || status === 'searching'

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium',
        config.className
      )}
    >
      {showIcon && (
        <Icon className={cn('w-3.5 h-3.5', isAnimated && 'animate-spin')} />
      )}
      {config.label}
    </span>
  )
}
