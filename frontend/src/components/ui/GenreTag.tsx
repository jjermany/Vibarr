'use client'

import Link from 'next/link'
import { cn } from '@/lib/utils'

interface GenreTagProps {
  genre: string
  size?: 'sm' | 'md'
  interactive?: boolean
}

const genreColors: Record<string, string> = {
  rock: 'bg-red-500/20 text-red-400 hover:bg-red-500/30',
  pop: 'bg-pink-500/20 text-pink-400 hover:bg-pink-500/30',
  'hip hop': 'bg-amber-500/20 text-amber-400 hover:bg-amber-500/30',
  rap: 'bg-amber-500/20 text-amber-400 hover:bg-amber-500/30',
  electronic: 'bg-cyan-500/20 text-cyan-400 hover:bg-cyan-500/30',
  jazz: 'bg-purple-500/20 text-purple-400 hover:bg-purple-500/30',
  classical: 'bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30',
  metal: 'bg-slate-500/20 text-slate-400 hover:bg-slate-500/30',
  indie: 'bg-orange-500/20 text-orange-400 hover:bg-orange-500/30',
  'r&b': 'bg-violet-500/20 text-violet-400 hover:bg-violet-500/30',
  soul: 'bg-violet-500/20 text-violet-400 hover:bg-violet-500/30',
  country: 'bg-yellow-500/20 text-yellow-400 hover:bg-yellow-500/30',
  blues: 'bg-blue-500/20 text-blue-400 hover:bg-blue-500/30',
  folk: 'bg-lime-500/20 text-lime-400 hover:bg-lime-500/30',
  punk: 'bg-rose-500/20 text-rose-400 hover:bg-rose-500/30',
  alternative: 'bg-teal-500/20 text-teal-400 hover:bg-teal-500/30',
}

function getGenreColor(genre: string): string {
  const normalizedGenre = genre.toLowerCase()
  for (const [key, value] of Object.entries(genreColors)) {
    if (normalizedGenre.includes(key)) {
      return value
    }
  }
  return 'bg-surface-700 text-surface-300 hover:bg-surface-600'
}

export function GenreTag({ genre, size = 'md', interactive = true }: GenreTagProps) {
  const sizeClasses = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-3 py-1 text-sm',
  }

  const className = cn(
    'rounded-full font-medium transition-colors',
    sizeClasses[size],
    getGenreColor(genre),
    interactive && 'cursor-pointer'
  )

  if (interactive) {
    return (
      <Link href={`/explore/genre/${encodeURIComponent(genre)}`} className={className}>
        {genre}
      </Link>
    )
  }

  return <span className={className}>{genre}</span>
}
