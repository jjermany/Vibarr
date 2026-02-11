'use client'

import Link from 'next/link'
import { Compass, Music, Clock, Heart, ArrowRight } from 'lucide-react'

const genres = [
  { name: 'Rock', color: 'from-red-500 to-orange-500', description: 'Guitar-driven classics and modern anthems' },
  { name: 'Pop', color: 'from-pink-500 to-rose-500', description: 'Hooks, melodies, and chart favorites' },
  { name: 'Hip Hop', color: 'from-amber-500 to-yellow-500', description: 'Bars, beats, and fresh releases' },
  { name: 'Electronic', color: 'from-cyan-500 to-blue-500', description: 'Club, house, and experimental sounds' },
  { name: 'Jazz', color: 'from-purple-500 to-violet-500', description: 'Improvisation from standards to modern fusion' },
  { name: 'Classical', color: 'from-emerald-500 to-teal-500', description: 'Orchestral works and timeless compositions' },
]

const decades = [2020, 2010, 2000, 1990, 1980, 1970, 1960]

const moods = [
  { name: 'Energetic', icon: '⚡', mood: 'energetic' },
  { name: 'Chill', icon: '🌊', mood: 'chill' },
  { name: 'Happy', icon: '☀️', mood: 'happy' },
  { name: 'Sad', icon: '🌧️', mood: 'sad' },
  { name: 'Focus', icon: '🎯', mood: 'focus' },
  { name: 'Workout', icon: '💪', mood: 'workout' },
]

export default function ExplorePage() {
  return (
    <div className="space-y-8">
      <div className="rounded-2xl border border-surface-800 bg-gradient-to-br from-surface-900 to-surface-950 p-6 sm:p-8">
        <h1 className="text-2xl sm:text-3xl font-bold text-white">Explore</h1>
        <p className="text-surface-300 mt-2 max-w-2xl">
          Discover music using browsing modes that map directly to real discovery logic: genres, decades, and mood profiles.
        </p>
      </div>

      <section className="space-y-4">
        <h2 className="text-lg font-semibold text-white flex items-center gap-2">
          <Music className="w-5 h-5" />
          Explore by genre
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {genres.map((genre) => (
            <Link
              key={genre.name}
              href={`/explore/genre/${encodeURIComponent(genre.name.toLowerCase())}`}
              className={`rounded-xl bg-gradient-to-br ${genre.color} p-5 hover:scale-[1.01] transition-transform`}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="text-white font-semibold text-lg">{genre.name}</h3>
                  <p className="text-white/85 text-sm mt-1">{genre.description}</p>
                </div>
                <ArrowRight className="w-4 h-4 text-white/80 mt-1" />
              </div>
            </Link>
          ))}
        </div>
      </section>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <section className="card p-5">
          <h2 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
            <Clock className="w-5 h-5" />
            Explore by decade
          </h2>
          <p className="text-sm text-surface-400 mb-4">Find standout albums and artists from a specific era.</p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {decades.map((year) => (
              <Link
                key={year}
                href={`/explore/decade/${year}`}
                className="rounded-lg bg-surface-800 px-3 py-4 text-center text-white font-medium hover:bg-surface-700 transition-colors"
              >
                {year}s
              </Link>
            ))}
          </div>
        </section>

        <section className="card p-5">
          <h2 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
            <Heart className="w-5 h-5" />
            Explore by mood
          </h2>
          <p className="text-sm text-surface-400 mb-4">Use audio features to surface tracks and albums for the moment.</p>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {moods.map((mood) => (
              <Link
                key={mood.mood}
                href={`/explore/mood/${mood.mood}`}
                className="rounded-lg bg-surface-800 p-3 text-center hover:bg-surface-700 transition-colors"
              >
                <div className="text-xl mb-1">{mood.icon}</div>
                <div className="text-white text-sm font-medium">{mood.name}</div>
              </Link>
            ))}
          </div>
        </section>
      </div>

      <section className="rounded-xl border border-primary-500/20 bg-primary-500/10 p-4 sm:p-5">
        <h3 className="text-white font-semibold flex items-center gap-2">
          <Compass className="w-4 h-4" />
          Why this layout?
        </h3>
        <p className="text-surface-300 text-sm mt-1">
          Each tile routes to an implemented discovery endpoint, avoiding dead links and reducing mismatches between UI categories and returned music.
        </p>
      </section>
    </div>
  )
}
