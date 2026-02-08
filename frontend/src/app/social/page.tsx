'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Users,
  ListMusic,
  Activity,
  Plus,
  Globe,
  Lock,
  Trash2,
  Music2,
  Heart,
  Download,
  UserPlus,
  Library,
  Clock,
} from 'lucide-react'
import { socialApi } from '@/lib/api'
import type { SharedPlaylist, ActivityItem } from '@/lib/api'
import { cn, formatDate } from '@/lib/utils'

const ACTIVITY_ICONS: Record<string, any> = {
  listened: Music2,
  added_to_library: Library,
  added_to_wishlist: Heart,
  created_playlist: ListMusic,
  added_to_playlist: Plus,
  followed_user: UserPlus,
  shared_recommendation: Users,
  downloaded: Download,
}

const ACTIVITY_COLORS: Record<string, string> = {
  listened: 'text-blue-400 bg-blue-400/10',
  added_to_library: 'text-green-400 bg-green-400/10',
  added_to_wishlist: 'text-pink-400 bg-pink-400/10',
  created_playlist: 'text-purple-400 bg-purple-400/10',
  added_to_playlist: 'text-indigo-400 bg-indigo-400/10',
  followed_user: 'text-cyan-400 bg-cyan-400/10',
  shared_recommendation: 'text-yellow-400 bg-yellow-400/10',
  downloaded: 'text-emerald-400 bg-emerald-400/10',
}

export default function SocialPage() {
  const [activeTab, setActiveTab] = useState<'activity' | 'playlists'>('activity')
  const [showCreatePlaylist, setShowCreatePlaylist] = useState(false)
  const [newPlaylist, setNewPlaylist] = useState({ name: '', description: '', is_public: false })
  const queryClient = useQueryClient()

  const { data: activity } = useQuery({
    queryKey: ['global-activity'],
    queryFn: async () => {
      const res = await socialApi.getGlobalActivity(50)
      return res.data
    },
  })

  const { data: playlists } = useQuery({
    queryKey: ['shared-playlists'],
    queryFn: async () => {
      const res = await socialApi.listPlaylists()
      return res.data
    },
  })

  const createPlaylistMutation = useMutation({
    mutationFn: (data: { name: string; description?: string; is_public?: boolean }) =>
      socialApi.createPlaylist(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['shared-playlists'] })
      setShowCreatePlaylist(false)
      setNewPlaylist({ name: '', description: '', is_public: false })
    },
  })

  const deletePlaylistMutation = useMutation({
    mutationFn: (id: number) => socialApi.deletePlaylist(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['shared-playlists'] }),
  })

  const tabs = [
    { key: 'activity' as const, label: 'Activity Feed', icon: Activity },
    { key: 'playlists' as const, label: 'Shared Playlists', icon: ListMusic },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Social</h1>
        <p className="text-surface-400 mt-1">Activity feed, shared playlists, and community features</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-surface-800/50 p-1 rounded-lg w-fit">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={cn(
              'flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors',
              activeTab === tab.key
                ? 'bg-surface-700 text-white'
                : 'text-surface-400 hover:text-white'
            )}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Activity Feed */}
      {activeTab === 'activity' && (
        <div className="space-y-3">
          {activity && activity.length > 0 ? (
            activity.map((item: ActivityItem) => {
              const IconComponent = ACTIVITY_ICONS[item.activity_type] || Activity
              const colorClass = ACTIVITY_COLORS[item.activity_type] || 'text-surface-400 bg-surface-700'
              return (
                <div key={item.id} className="card p-4 flex items-start gap-3">
                  <div className={cn('w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0', colorClass)}>
                    <IconComponent className="w-4 h-4" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-white">
                      <span className="font-semibold">{item.user?.display_name || 'Someone'}</span>
                      {' '}
                      <span className="text-surface-300">{item.message || item.activity_type.replace(/_/g, ' ')}</span>
                    </p>
                    <p className="text-xs text-surface-500 mt-0.5 flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {formatDate(item.created_at)}
                    </p>
                  </div>
                </div>
              )
            })
          ) : (
            <div className="text-center py-12">
              <Activity className="w-12 h-12 text-surface-500 mx-auto mb-3" />
              <h3 className="text-lg font-semibold text-white">No Activity Yet</h3>
              <p className="text-surface-400 mt-1">
                Activity from you and people you follow will appear here.
              </p>
            </div>
          )}
        </div>
      )}

      {/* Shared Playlists */}
      {activeTab === 'playlists' && (
        <div className="space-y-4">
          {/* Create Playlist */}
          <div>
            {!showCreatePlaylist ? (
              <button
                onClick={() => setShowCreatePlaylist(true)}
                className="btn btn-primary flex items-center gap-2"
              >
                <Plus className="w-4 h-4" /> New Playlist
              </button>
            ) : (
              <div className="card p-4 space-y-3">
                <h4 className="text-white font-semibold">Create Shared Playlist</h4>
                <input
                  type="text"
                  placeholder="Playlist name"
                  value={newPlaylist.name}
                  onChange={(e) => setNewPlaylist({ ...newPlaylist, name: e.target.value })}
                  className="input w-full"
                />
                <input
                  type="text"
                  placeholder="Description (optional)"
                  value={newPlaylist.description}
                  onChange={(e) => setNewPlaylist({ ...newPlaylist, description: e.target.value })}
                  className="input w-full"
                />
                <label className="flex items-center gap-2 text-sm text-surface-300">
                  <input
                    type="checkbox"
                    checked={newPlaylist.is_public}
                    onChange={(e) => setNewPlaylist({ ...newPlaylist, is_public: e.target.checked })}
                    className="rounded"
                  />
                  Make public
                </label>
                <div className="flex gap-2">
                  <button
                    onClick={() => createPlaylistMutation.mutate(newPlaylist)}
                    disabled={!newPlaylist.name || createPlaylistMutation.isPending}
                    className="btn btn-primary text-sm"
                  >
                    Create
                  </button>
                  <button
                    onClick={() => setShowCreatePlaylist(false)}
                    className="btn btn-ghost text-sm"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Playlist List */}
          {playlists && playlists.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {playlists.map((playlist: SharedPlaylist) => (
                <div key={playlist.id} className="card p-4 hover:border-surface-600 transition-colors">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-primary-500/30 to-accent-500/30 flex items-center justify-center">
                        <ListMusic className="w-6 h-6 text-primary-400" />
                      </div>
                      <div>
                        <h4 className="text-white font-semibold">{playlist.name}</h4>
                        <p className="text-surface-400 text-sm">
                          {playlist.total_tracks} tracks
                          {playlist.owner && ` by ${playlist.owner.display_name}`}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      {playlist.is_public ? (
                        <Globe className="w-4 h-4 text-surface-500" />
                      ) : (
                        <Lock className="w-4 h-4 text-surface-500" />
                      )}
                      <button
                        onClick={() => deletePlaylistMutation.mutate(playlist.id)}
                        className="p-1 text-surface-500 hover:text-red-400 transition-colors"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                  {playlist.description && (
                    <p className="text-surface-400 text-sm mt-2 line-clamp-2">{playlist.description}</p>
                  )}
                  {playlist.collaborative && (
                    <span className="inline-block mt-2 px-2 py-0.5 bg-accent-500/20 text-accent-400 rounded text-xs">
                      Collaborative
                    </span>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-12">
              <ListMusic className="w-12 h-12 text-surface-500 mx-auto mb-3" />
              <h3 className="text-lg font-semibold text-white">No Shared Playlists</h3>
              <p className="text-surface-400 mt-1">
                Create a playlist to share music with others.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
