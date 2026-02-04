'use client'

import Link from 'next/link'
import { ChevronRight } from 'lucide-react'

interface SectionHeaderProps {
  title: string
  description?: string
  href?: string
  action?: React.ReactNode
}

export function SectionHeader({
  title,
  description,
  href,
  action,
}: SectionHeaderProps) {
  return (
    <div className="flex items-center justify-between mb-4">
      <div>
        <h2 className="text-xl font-bold text-white">{title}</h2>
        {description && (
          <p className="text-sm text-surface-400 mt-0.5">{description}</p>
        )}
      </div>
      {href ? (
        <Link
          href={href}
          className="flex items-center gap-1 text-sm font-medium text-surface-400 hover:text-white transition-colors"
        >
          See all
          <ChevronRight className="w-4 h-4" />
        </Link>
      ) : (
        action
      )}
    </div>
  )
}
