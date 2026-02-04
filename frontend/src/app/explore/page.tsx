'use client'

import Link from 'next/link'
import { Compass, Music, Clock, Sparkles, Heart } from 'lucide-react'

const genres = [
  { name: 'Rock', color: 'from-red-500 to-orange-500' },
  { name: 'Pop', color: 'from-pink-500 to-rose-500' },
  { name: 'Hip Hop', color: 'from-amber-500 to-yellow-500' },
  { name: 'Electronic', color: 'from-cyan-500 to-blue-500' },
  { name: 'Jazz', color: 'from-purple-500 to-violet-500' },
  { name: 'Classical', color: 'from-emerald-500 to-teal-500' },
  { name: 'Metal', color: 'from-slate-500 to-zinc-500' },
  { name: 'Indie', color: 'from-orange-500 to-amber-500' },
  { name: 'R&B', color: 'from-violet-500 to-purple-500' },
  { name: 'Country', color: 'from-yellow-500 to-lime-500' },
  { name: 'Blues', color: 'from-blue-500 to-indigo-500' },
  { name: 'Folk', color: 'from-lime-500 to-green-500' },
]

const decades = [
  { name: '2020s', year: 2020 },
  { name: '2010s', year: 2010 },
  { name: '2000s', year: 2000 },
  { name: '1990s', year: 1990 },
  { name: '1980s', year: 1980 },
  { name: '1970s', year: 1970 },
  { name: '1960s', year: 1960 },
]

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
    <div className="space-y-10">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Explore</h1>
        <p className="text-surface-400 mt-1">
          Discover new music by genre, decade, or mood
        </p>
      </div>

      {/* Browse by Genre */}
      <section>
        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Music className="w-5 h-5" />
          Browse by Genre
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
          {genres.map((genre) => (
            <Link
              key={genre.name}
              href={`/explore/genre/${encodeURIComponent(genre.name.toLowerCase())}`}
              className={`aspect-square rounded-xl bg-gradient-to-br ${genre.color} p-4 flex items-end hover:scale-105 transition-transform`}
            >
              <span className="text-white font-bold text-lg">{genre.name}</span>
            </Link>
          ))}
        </div>
      </section>

      {/* Browse by Decade */}
      <section>
        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Clock className="w-5 h-5" />
          Time Machine
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-7 gap-4">
          {decades.map((decade) => (
            <Link
              key={decade.year}
              href={`/explore/decade/${decade.year}`}
              className="card-hover p-4 text-center"
            >
              <span className="text-2xl font-bold text-white">{decade.name}</span>
            </Link>
          ))}
        </div>
      </section>

      {/* Browse by Mood */}
      <section>
        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Heart className="w-5 h-5" />
          Browse by Mood
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-4">
          {moods.map((mood) => (
            <Link
              key={mood.mood}
              href={`/explore/mood/${mood.mood}`}
              className="card-hover p-6 text-center"
            >
              <span className="text-3xl mb-2 block">{mood.icon}</span>
              <span className="text-white font-medium">{mood.name}</span>
            </Link>
          ))}
        </div>
      </section>

      {/* Quick Links */}
      <section>
        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Sparkles className="w-5 h-5" />
          Quick Discover
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <Link
            href="/explore/new-releases"
            className="card-hover p-6 flex items-center gap-4"
          >
            <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-green-500 to-emerald-500 flex items-center justify-center">
              <Sparkles className="w-6 h-6 text-white" />
            </div>
            <div>
              <h3 className="font-semibold text-white">New Releases</h3>
              <p className="text-sm text-surface-400">Latest albums this week</p>
            </div>
          </Link>

          <Link
            href="/explore/trending"
            className="card-hover p-6 flex items-center gap-4"
          >
            <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-orange-500 to-red-500 flex items-center justify-center">
              <Compass className="w-6 h-6 text-white" />
            </div>
            <div>
              <h3 className="font-semibold text-white">Trending</h3>
              <p className="text-sm text-surface-400">What&apos;s popular now</p>
            </div>
          </Link>

          <Link
            href="/explore/underrated"
            className="card-hover p-6 flex items-center gap-4"
          >
            <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
              <Heart className="w-6 h-6 text-white" />
            </div>
            <div>
              <h3 className="font-semibold text-white">Hidden Gems</h3>
              <p className="text-sm text-surface-400">Underrated discoveries</p>
            </div>
          </Link>
        </div>
      </section>
    </div>
  )
}
