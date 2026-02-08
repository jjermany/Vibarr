'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart3,
  Clock,
  Disc3,
  Flame,
  Music,
  TrendingUp,
  TrendingDown,
  Users,
  Headphones,
  Sparkles,
  Calendar,
  Target,
} from 'lucide-react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  AreaChart,
  Area,
  LineChart,
  Line,
} from 'recharts'
import { statsApi } from '@/lib/api'
import { LoadingPage } from '@/components/ui/LoadingSpinner'
import { EmptyState } from '@/components/ui/EmptyState'
import { cn } from '@/lib/utils'

const PERIOD_OPTIONS = [
  { label: '7d', value: 7 },
  { label: '30d', value: 30 },
  { label: '90d', value: 90 },
  { label: '1y', value: 365 },
]

const GENRE_COLORS = [
  '#0ea5e9', '#d946ef', '#f97316', '#22c55e', '#eab308',
  '#ef4444', '#8b5cf6', '#06b6d4', '#f43f5e', '#14b8a6',
]

const HOUR_LABELS: Record<number, string> = {
  0: '12a', 3: '3a', 6: '6a', 9: '9a',
  12: '12p', 15: '3p', 18: '6p', 21: '9p',
}

export default function StatsPage() {
  const [days, setDays] = useState(30)

  const { data: overview, isLoading: overviewLoading } = useQuery({
    queryKey: ['stats', 'overview', days],
    queryFn: () => statsApi.overview(days),
  })

  const { data: streak } = useQuery({
    queryKey: ['stats', 'streak'],
    queryFn: () => statsApi.streak(),
  })

  const { data: comparison } = useQuery({
    queryKey: ['stats', 'comparison', days],
    queryFn: () => statsApi.comparison(days),
  })

  const { data: listeningTime } = useQuery({
    queryKey: ['stats', 'listening-time', days],
    queryFn: () => statsApi.listeningTime(days, days <= 30 ? 'day' : 'week'),
  })

  const { data: patterns } = useQuery({
    queryKey: ['stats', 'patterns', days],
    queryFn: () => statsApi.listeningPatterns(days),
  })

  const { data: audioFeatures } = useQuery({
    queryKey: ['stats', 'audio-features', days],
    queryFn: () => statsApi.audioFeatures(days),
  })

  const { data: genres } = useQuery({
    queryKey: ['stats', 'genres', days],
    queryFn: () => statsApi.topGenres(days, 10),
  })

  const { data: decades } = useQuery({
    queryKey: ['stats', 'decades', days],
    queryFn: () => statsApi.decadeBreakdown(days),
  })

  const { data: discovery } = useQuery({
    queryKey: ['stats', 'discovery', days],
    queryFn: () => statsApi.discoveryStats(days),
  })

  const { data: libraryGrowth } = useQuery({
    queryKey: ['stats', 'library-growth', days],
    queryFn: () => statsApi.libraryGrowth(days),
  })

  const { data: topTracks } = useQuery({
    queryKey: ['stats', 'top-tracks', days],
    queryFn: () => statsApi.topTracks(days, 10),
  })

  if (overviewLoading) {
    return <LoadingPage message="Crunching your listening data..." />
  }

  const stats = overview?.data
  const streakData = streak?.data
  const comparisonData = comparison?.data
  const timeData = listeningTime?.data?.data || []
  const patternData = patterns?.data
  const featureData = audioFeatures?.data
  const genreData = genres?.data?.genres || []
  const decadeData = decades?.data?.decades || []
  const discoveryData = discovery?.data
  const growthData = libraryGrowth?.data?.growth || []
  const topTracksData = topTracks?.data?.tracks || []

  if (!stats) {
    return (
      <EmptyState
        icon={<BarChart3 className="w-8 h-8" />}
        title="No listening data yet"
        description="Start listening to music through Plex to see your stats and insights"
      />
    )
  }

  // Build radar chart data
  const radarData = featureData
    ? [
        { feature: 'Dance', value: featureData.avg_danceability, fullMark: 1 },
        { feature: 'Energy', value: featureData.avg_energy, fullMark: 1 },
        { feature: 'Happy', value: featureData.avg_valence, fullMark: 1 },
        { feature: 'Acoustic', value: featureData.avg_acousticness, fullMark: 1 },
        { feature: 'Instrumental', value: featureData.avg_instrumentalness, fullMark: 1 },
        { feature: 'Live', value: featureData.avg_liveness, fullMark: 1 },
      ]
    : []

  // Build hourly heatmap data
  const hourlyData = (patternData?.hourly_distribution || []).map(
    (h: { hour: number; play_count: number }) => ({
      hour: h.hour,
      label: HOUR_LABELS[h.hour] || `${h.hour}`,
      plays: h.play_count,
    })
  )

  // Build daily data
  const dayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
  const dailyData = (patternData?.daily_distribution || []).map(
    (d: { day: number; play_count: number }) => ({
      day: dayNames[d.day] || 'Unknown',
      plays: d.play_count,
    })
  )

  // Format listening time chart
  const formattedTimeData = timeData.map(
    (d: { period: string; play_count: number; total_time_hours: number }) => ({
      date: d.period ? new Date(d.period).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : '',
      plays: d.play_count,
      hours: d.total_time_hours,
    })
  )

  // Trim growth data to show at most 90 points
  const trimmedGrowth = growthData.length > 90
    ? growthData.filter((_: unknown, i: number) => i % Math.ceil(growthData.length / 90) === 0)
    : growthData
  const formattedGrowth = trimmedGrowth.map(
    (d: { date: string; total: number; added: number }) => ({
      date: new Date(d.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      total: d.total,
      added: d.added,
    })
  )

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Stats & Insights</h1>
          <p className="text-surface-400 text-sm mt-1">
            Your music listening habits at a glance
          </p>
        </div>
        <div className="flex bg-surface-800 rounded-lg p-1">
          {PERIOD_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setDays(opt.value)}
              className={cn(
                'px-3 py-1.5 rounded-md text-sm font-medium transition-colors',
                days === opt.value
                  ? 'bg-primary-600 text-white'
                  : 'text-surface-400 hover:text-white'
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          icon={<Headphones className="w-5 h-5" />}
          label="Total Plays"
          value={stats.total_plays.toLocaleString()}
          change={comparisonData?.changes?.plays_pct}
          color="text-primary-400"
        />
        <StatCard
          icon={<Clock className="w-5 h-5" />}
          label="Listening Time"
          value={`${stats.total_time_hours}h`}
          change={comparisonData?.changes?.time_pct}
          color="text-accent-400"
        />
        <StatCard
          icon={<Users className="w-5 h-5" />}
          label="Artists"
          value={stats.unique_artists.toLocaleString()}
          change={comparisonData?.changes?.artists_pct}
          color="text-green-400"
        />
        <StatCard
          icon={<Flame className="w-5 h-5" />}
          label="Streak"
          value={`${streakData?.current_streak || 0}d`}
          subtitle={`Best: ${streakData?.longest_streak || 0}d`}
          color="text-orange-400"
        />
      </div>

      {/* Discovery Stats */}
      {discoveryData && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <MiniStat
            icon={<Sparkles className="w-4 h-4 text-purple-400" />}
            label="New Artists"
            value={discoveryData.new_artists_discovered}
          />
          <MiniStat
            icon={<Disc3 className="w-4 h-4 text-blue-400" />}
            label="New Albums"
            value={discoveryData.new_albums_discovered}
          />
          <MiniStat
            icon={<Target className="w-4 h-4 text-green-400" />}
            label="Recs Clicked"
            value={discoveryData.recommendations_clicked}
          />
          <MiniStat
            icon={<TrendingUp className="w-4 h-4 text-orange-400" />}
            label="Discovery Rate"
            value={`${discoveryData.discovery_rate}%`}
          />
        </div>
      )}

      {/* Charts Row 1: Listening Time + Genre Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Listening Time Chart */}
        <div className="lg:col-span-2 card p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Listening Activity</h3>
          {formattedTimeData.length > 0 ? (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={formattedTimeData}>
                  <defs>
                    <linearGradient id="colorPlays" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#0ea5e9" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#0ea5e9" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                  <XAxis
                    dataKey="date"
                    stroke="#71717a"
                    fontSize={12}
                    tickLine={false}
                  />
                  <YAxis stroke="#71717a" fontSize={12} tickLine={false} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#18181b',
                      border: '1px solid #3f3f46',
                      borderRadius: '8px',
                      color: '#fff',
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="plays"
                    stroke="#0ea5e9"
                    strokeWidth={2}
                    fill="url(#colorPlays)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="h-64 flex items-center justify-center text-surface-500">
              No listening data for this period
            </div>
          )}
        </div>

        {/* Genre Distribution */}
        <div className="card p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Top Genres</h3>
          {genreData.length > 0 ? (
            <>
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={genreData.slice(0, 6)}
                      cx="50%"
                      cy="50%"
                      innerRadius={40}
                      outerRadius={70}
                      paddingAngle={3}
                      dataKey="play_count"
                      nameKey="genre"
                    >
                      {genreData.slice(0, 6).map((_: unknown, i: number) => (
                        <Cell key={i} fill={GENRE_COLORS[i % GENRE_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#18181b',
                        border: '1px solid #3f3f46',
                        borderRadius: '8px',
                        color: '#fff',
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="space-y-2 mt-2">
                {genreData.slice(0, 6).map((g: { genre: string; percentage: number }, i: number) => (
                  <div key={g.genre} className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <div
                        className="w-3 h-3 rounded-full"
                        style={{ backgroundColor: GENRE_COLORS[i % GENRE_COLORS.length] }}
                      />
                      <span className="text-surface-300 capitalize">{g.genre}</span>
                    </div>
                    <span className="text-surface-400">{g.percentage}%</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="h-48 flex items-center justify-center text-surface-500">
              No genre data available
            </div>
          )}
        </div>
      </div>

      {/* Charts Row 2: Audio Profile + Listening Patterns */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Audio Feature Radar */}
        <div className="card p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Your Audio Profile</h3>
          {radarData.length > 0 ? (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart data={radarData}>
                  <PolarGrid stroke="#3f3f46" />
                  <PolarAngleAxis
                    dataKey="feature"
                    stroke="#a1a1aa"
                    fontSize={12}
                  />
                  <PolarRadiusAxis
                    angle={30}
                    domain={[0, 1]}
                    tick={false}
                    axisLine={false}
                  />
                  <Radar
                    dataKey="value"
                    stroke="#d946ef"
                    fill="#d946ef"
                    fillOpacity={0.3}
                    strokeWidth={2}
                  />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="h-64 flex items-center justify-center text-surface-500">
              No audio feature data yet
            </div>
          )}
        </div>

        {/* Listening Patterns */}
        <div className="card p-6">
          <h3 className="text-lg font-semibold text-white mb-4">When You Listen</h3>
          <div className="space-y-6">
            {/* Hourly */}
            {hourlyData.length > 0 && (
              <div>
                <p className="text-sm text-surface-400 mb-2">By Hour</p>
                <div className="h-28">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={hourlyData}>
                      <XAxis
                        dataKey="label"
                        stroke="#71717a"
                        fontSize={10}
                        tickLine={false}
                        interval={2}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: '#18181b',
                          border: '1px solid #3f3f46',
                          borderRadius: '8px',
                          color: '#fff',
                        }}
                      />
                      <Bar dataKey="plays" fill="#0ea5e9" radius={[2, 2, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}

            {/* Day of Week */}
            {dailyData.length > 0 && (
              <div>
                <p className="text-sm text-surface-400 mb-2">By Day of Week</p>
                <div className="h-28">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={dailyData}>
                      <XAxis
                        dataKey="day"
                        stroke="#71717a"
                        fontSize={11}
                        tickLine={false}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: '#18181b',
                          border: '1px solid #3f3f46',
                          borderRadius: '8px',
                          color: '#fff',
                        }}
                      />
                      <Bar dataKey="plays" fill="#d946ef" radius={[2, 2, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Charts Row 3: Top Artists + Top Tracks */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top Artists */}
        <div className="card p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Top Artists</h3>
          <div className="space-y-3">
            {(stats.top_artists || []).map(
              (artist: { id: number; name: string; image_url?: string; play_count: number; total_time_ms: number }, i: number) => (
                <div key={artist.id} className="flex items-center gap-3">
                  <span className="text-surface-500 text-sm w-5 text-right">{i + 1}</span>
                  <div className="w-10 h-10 rounded-full bg-surface-800 overflow-hidden flex-shrink-0">
                    {artist.image_url ? (
                      <img
                        src={artist.image_url}
                        alt={artist.name}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-surface-500">
                        <Music className="w-4 h-4" />
                      </div>
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-white text-sm font-medium truncate">{artist.name}</p>
                    <p className="text-surface-500 text-xs">
                      {artist.play_count} plays
                      {' '}&middot;{' '}
                      {Math.round(artist.total_time_ms / (1000 * 60))} min
                    </p>
                  </div>
                  <div className="flex-shrink-0">
                    <div className="w-24 h-1.5 bg-surface-800 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-primary-500 rounded-full"
                        style={{
                          width: `${Math.min(
                            (artist.play_count /
                              Math.max(stats.top_artists[0]?.play_count || 1, 1)) *
                              100,
                            100
                          )}%`,
                        }}
                      />
                    </div>
                  </div>
                </div>
              )
            )}
            {(stats.top_artists || []).length === 0 && (
              <p className="text-surface-500 text-sm text-center py-4">
                No artist data for this period
              </p>
            )}
          </div>
        </div>

        {/* Top Tracks */}
        <div className="card p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Top Tracks</h3>
          <div className="space-y-3">
            {topTracksData.map(
              (track: { id: number; title: string; artist_name: string; play_count: number; skip_rate: number }, i: number) => (
                <div key={track.id} className="flex items-center gap-3">
                  <span className="text-surface-500 text-sm w-5 text-right">{i + 1}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-white text-sm font-medium truncate">{track.title}</p>
                    <p className="text-surface-500 text-xs truncate">{track.artist_name}</p>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <p className="text-surface-300 text-sm">{track.play_count} plays</p>
                    {track.skip_rate > 0 && (
                      <p className="text-surface-500 text-xs">
                        {Math.round(track.skip_rate * 100)}% skip
                      </p>
                    )}
                  </div>
                </div>
              )
            )}
            {topTracksData.length === 0 && (
              <p className="text-surface-500 text-sm text-center py-4">
                No track data for this period
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Charts Row 4: Decade Breakdown + Library Growth */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Decade Breakdown */}
        <div className="card p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Decades</h3>
          {decadeData.length > 0 ? (
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={decadeData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                  <XAxis
                    dataKey="label"
                    stroke="#71717a"
                    fontSize={12}
                    tickLine={false}
                  />
                  <YAxis stroke="#71717a" fontSize={12} tickLine={false} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#18181b',
                      border: '1px solid #3f3f46',
                      borderRadius: '8px',
                      color: '#fff',
                    }}
                  />
                  <Bar dataKey="play_count" fill="#22c55e" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="h-48 flex items-center justify-center text-surface-500">
              No decade data available
            </div>
          )}
        </div>

        {/* Library Growth */}
        <div className="card p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Library Growth</h3>
          {formattedGrowth.length > 0 ? (
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={formattedGrowth}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                  <XAxis
                    dataKey="date"
                    stroke="#71717a"
                    fontSize={12}
                    tickLine={false}
                  />
                  <YAxis stroke="#71717a" fontSize={12} tickLine={false} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#18181b',
                      border: '1px solid #3f3f46',
                      borderRadius: '8px',
                      color: '#fff',
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="total"
                    stroke="#f97316"
                    strokeWidth={2}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="h-48 flex items-center justify-center text-surface-500">
              No growth data available
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function StatCard({
  icon,
  label,
  value,
  change,
  subtitle,
  color,
}: {
  icon: React.ReactNode
  label: string
  value: string
  change?: number
  subtitle?: string
  color: string
}) {
  return (
    <div className="card p-5">
      <div className="flex items-center justify-between mb-3">
        <span className={color}>{icon}</span>
        {change !== undefined && change !== null && (
          <span
            className={cn(
              'flex items-center gap-1 text-xs font-medium',
              change >= 0 ? 'text-green-400' : 'text-red-400'
            )}
          >
            {change >= 0 ? (
              <TrendingUp className="w-3 h-3" />
            ) : (
              <TrendingDown className="w-3 h-3" />
            )}
            {Math.abs(change)}%
          </span>
        )}
      </div>
      <p className="text-2xl font-bold text-white">{value}</p>
      {subtitle ? (
        <p className="text-xs text-surface-500 mt-1">{subtitle}</p>
      ) : (
        <p className="text-xs text-surface-500 mt-1">{label}</p>
      )}
    </div>
  )
}

function MiniStat({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode
  label: string
  value: string | number
}) {
  return (
    <div className="card p-4 flex items-center gap-3">
      <div className="w-8 h-8 rounded-lg bg-surface-800 flex items-center justify-center">
        {icon}
      </div>
      <div>
        <p className="text-lg font-semibold text-white">{value}</p>
        <p className="text-xs text-surface-500">{label}</p>
      </div>
    </div>
  )
}
