'use client'

import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  User,
  Users,
  Shield,
  Eye,
  Sparkles,
  Languages,
  Save,
} from 'lucide-react'
import { authApi } from '@/lib/api'
import toast from 'react-hot-toast'
import { cn } from '@/lib/utils'

const CLUSTER_LABELS: Record<string, { label: string; emoji: string; color: string }> = {
  energetic_explorer: { label: 'Energetic Explorer', emoji: '⚡', color: 'from-yellow-500 to-orange-500' },
  chill_curator: { label: 'Chill Curator', emoji: '🌊', color: 'from-cyan-500 to-blue-500' },
  eclectic_audiophile: { label: 'Eclectic Audiophile', emoji: '🎧', color: 'from-purple-500 to-pink-500' },
  rhythm_devotee: { label: 'Rhythm Devotee', emoji: '🥁', color: 'from-red-500 to-pink-500' },
  melancholy_romantic: { label: 'Melancholy Romantic', emoji: '🌙', color: 'from-indigo-500 to-purple-500' },
  instrumental_voyager: { label: 'Instrumental Voyager', emoji: '🎻', color: 'from-emerald-500 to-teal-500' },
  indie_tastemaker: { label: 'Indie Tastemaker', emoji: '🎸', color: 'from-amber-500 to-yellow-500' },
  high_fidelity_purist: { label: 'High Fidelity Purist', emoji: '🎵', color: 'from-slate-500 to-zinc-500' },
}

export default function ProfilePage() {
  const [activeTab, setActiveTab] = useState<'profile' | 'users'>('profile')
  const [preferredLanguage, setPreferredLanguage] = useState('')
  const [secondaryLanguages, setSecondaryLanguages] = useState('')
  const queryClient = useQueryClient()

  const { data: profile } = useQuery({
    queryKey: ['profile'],
    queryFn: async () => {
      const res = await authApi.getProfile()
      return res.data
    },
    retry: false,
  })

  const { data: users } = useQuery({
    queryKey: ['users'],
    queryFn: async () => {
      const res = await authApi.listUsers()
      return res.data
    },
  })


  useEffect(() => {
    if (!profile) return
    setPreferredLanguage(profile.preferred_language || '')
    setSecondaryLanguages((profile.secondary_languages || []).join(', '))
  }, [profile])

  const updateProfileMutation = useMutation({
    mutationFn: () =>
      authApi.updateProfile({
        preferred_language: preferredLanguage.trim() || undefined,
        secondary_languages: secondaryLanguages
          .split(',')
          .map((language) => language.trim().toLowerCase())
          .filter(Boolean),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profile'] })
      toast.success('Language preferences saved')
    },
    onError: () => toast.error('Failed to save language preferences'),
  })

  const tabs = [
    { key: 'profile' as const, label: 'My Profile', icon: User },
    { key: 'users' as const, label: 'Users', icon: Users },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Profile</h1>
        <p className="text-surface-400 mt-1">Manage your profile, taste identity, and discover other users</p>
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

      {activeTab === 'profile' && (
        <div className="space-y-6">
          {/* Taste Identity Card */}
          {profile?.taste_cluster && (
            <div className={cn(
              'rounded-xl p-6 bg-gradient-to-br',
              CLUSTER_LABELS[profile.taste_cluster]?.color || 'from-primary-500 to-accent-500',
              'bg-opacity-20'
            )}>
              <div className="flex items-start gap-4">
                <div className="w-16 h-16 rounded-2xl bg-white/10 backdrop-blur flex items-center justify-center text-3xl">
                  {CLUSTER_LABELS[profile.taste_cluster]?.emoji || '🎵'}
                </div>
                <div>
                  <p className="text-sm text-white/70 font-medium">Your Taste Identity</p>
                  <h2 className="text-2xl font-bold text-white">
                    {CLUSTER_LABELS[profile.taste_cluster]?.label || profile.taste_cluster}
                  </h2>
                  <div className="flex flex-wrap gap-2 mt-3">
                    {(profile.taste_tags || []).map((tag: string, i: number) => (
                      <span
                        key={i}
                        className="px-3 py-1 bg-white/10 backdrop-blur rounded-full text-sm text-white/90"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {!profile?.taste_cluster && (
            <div className="card p-6 text-center">
              <Sparkles className="w-12 h-12 text-surface-500 mx-auto mb-3" />
              <h3 className="text-lg font-semibold text-white">Taste Profile Building</h3>
              <p className="text-surface-400 mt-1 max-w-md mx-auto">
                Keep listening to music and your ML taste profile will be computed automatically.
                The more you listen, the more accurate your taste identity becomes.
              </p>
            </div>
          )}

          {/* Profile Info */}
          <div className="card p-6">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <User className="w-5 h-5 text-primary-400" />
              Account Details
            </h3>
            {profile ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="text-sm text-surface-400">Username</label>
                  <p className="text-white font-medium">{profile.username}</p>
                </div>
                <div>
                  <label className="text-sm text-surface-400">Display Name</label>
                  <p className="text-white font-medium">{profile.display_name}</p>
                </div>
                <div>
                  <label className="text-sm text-surface-400">Email</label>
                  <p className="text-white font-medium">{profile.email}</p>
                </div>
                <div>
                  <label className="text-sm text-surface-400">Role</label>
                  <p className="text-white font-medium flex items-center gap-1">
                    {profile.is_admin ? (
                      <><Shield className="w-4 h-4 text-yellow-400" /> Admin</>
                    ) : (
                      'Member'
                    )}
                  </p>
                </div>
              </div>
            ) : (
              <div className="text-center py-8">
                <p className="text-surface-400">
                  No account found. Create one in Settings to enable multi-user features.
                </p>
              </div>
            )}
          </div>

          {profile && (
            <div className="card p-6">
              <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <Languages className="w-5 h-5 text-primary-400" />
                Language Preferences
              </h3>
              <p className="text-surface-400 text-sm mb-4">
                Discovery uses these languages when external providers expose language metadata.
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="text-sm text-surface-400 block mb-1">Preferred language</label>
                  <input
                    value={preferredLanguage}
                    onChange={(e) => setPreferredLanguage(e.target.value)}
                    placeholder="e.g. en, es, fr"
                    className="w-full bg-surface-900 border border-surface-700 rounded px-3 py-2 text-white"
                  />
                </div>
                <div>
                  <label className="text-sm text-surface-400 block mb-1">Secondary languages</label>
                  <input
                    value={secondaryLanguages}
                    onChange={(e) => setSecondaryLanguages(e.target.value)}
                    placeholder="Comma-separated, e.g. es, pt-br"
                    className="w-full bg-surface-900 border border-surface-700 rounded px-3 py-2 text-white"
                  />
                </div>
              </div>
              <button
                onClick={() => updateProfileMutation.mutate()}
                disabled={updateProfileMutation.isPending}
                className="mt-4 inline-flex items-center gap-2 px-3 py-2 rounded bg-primary-600 hover:bg-primary-500 disabled:opacity-60 text-white"
              >
                <Save className="w-4 h-4" />
                Save language settings
              </button>
            </div>
          )}

          {/* Privacy Settings */}
          {profile && (
            <div className="card p-6">
              <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <Eye className="w-5 h-5 text-primary-400" />
                Privacy
              </h3>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-white text-sm font-medium">Public Profile</p>
                    <p className="text-surface-400 text-xs">Others can see your profile</p>
                  </div>
                  <span className={cn(
                    'px-2 py-0.5 rounded text-xs font-medium',
                    profile.profile_public ? 'bg-green-500/20 text-green-400' : 'bg-surface-700 text-surface-400'
                  )}>
                    {profile.profile_public ? 'Public' : 'Private'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-white text-sm font-medium">Share Listening Activity</p>
                    <p className="text-surface-400 text-xs">Show what you're listening to</p>
                  </div>
                  <span className={cn(
                    'px-2 py-0.5 rounded text-xs font-medium',
                    profile.share_listening_activity ? 'bg-green-500/20 text-green-400' : 'bg-surface-700 text-surface-400'
                  )}>
                    {profile.share_listening_activity ? 'Sharing' : 'Hidden'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-white text-sm font-medium">Share Library</p>
                    <p className="text-surface-400 text-xs">Others can browse your library</p>
                  </div>
                  <span className={cn(
                    'px-2 py-0.5 rounded text-xs font-medium',
                    profile.share_library ? 'bg-green-500/20 text-green-400' : 'bg-surface-700 text-surface-400'
                  )}>
                    {profile.share_library ? 'Sharing' : 'Hidden'}
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {activeTab === 'users' && (
        <div className="space-y-4">
          {users && users.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {users.map((user: any) => {
                const cluster = CLUSTER_LABELS[user.taste_cluster] || null
                return (
                  <div key={user.id} className="card p-4 hover:border-surface-600 transition-colors">
                    <div className="flex items-start gap-3">
                      <div className="w-12 h-12 rounded-full bg-gradient-to-br from-primary-500 to-accent-500 flex items-center justify-center text-white font-bold text-lg">
                        {(user.display_name || user.username).charAt(0).toUpperCase()}
                      </div>
                      <div className="flex-1 min-w-0">
                        <h4 className="text-white font-semibold truncate">{user.display_name || user.username}</h4>
                        <p className="text-surface-400 text-sm">@{user.username}</p>
                        {cluster && (
                          <p className="text-xs mt-1 text-surface-300">
                            {cluster.emoji} {cluster.label}
                          </p>
                        )}
                        {user.taste_tags && user.taste_tags.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-2">
                            {user.taste_tags.slice(0, 3).map((tag: string, i: number) => (
                              <span key={i} className="px-2 py-0.5 bg-surface-700 rounded text-xs text-surface-300">
                                {tag}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <div className="text-center py-12">
              <Users className="w-12 h-12 text-surface-500 mx-auto mb-3" />
              <h3 className="text-lg font-semibold text-white">No Other Users Yet</h3>
              <p className="text-surface-400 mt-1">
                Share the registration link with household members to get started.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
