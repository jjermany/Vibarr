'use client'

import { useState, useEffect, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Settings,
  Download,
  Music2,
  Shield,
  CheckCircle,
  XCircle,
  AlertCircle,
  Plus,
  Trash2,
  Edit2,
  Server,
  HardDrive,
  Save,
  Eye,
  EyeOff,
  Loader2,
} from 'lucide-react'
import {
  settingsApi,
  type QualityProfile,
  type ServiceStatus,
  type GeneralSettings,
} from '@/lib/api'
import { LoadingPage } from '@/components/ui/LoadingSpinner'
import { cn } from '@/lib/utils'
import toast from 'react-hot-toast'

type Tab = 'services' | 'quality' | 'automation'

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<Tab>('services')

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Settings</h1>
        <p className="text-surface-400 mt-1">
          Configure services, quality preferences, and download automation
        </p>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 border-b border-surface-800">
        {([
          { id: 'services' as Tab, label: 'Services', icon: Server },
          { id: 'quality' as Tab, label: 'Quality Profiles', icon: Music2 },
          { id: 'automation' as Tab, label: 'Automation', icon: Download },
        ]).map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              'flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors',
              activeTab === tab.id
                ? 'border-primary-500 text-primary-400'
                : 'border-transparent text-surface-400 hover:text-white'
            )}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === 'services' && <ServicesTab />}
      {activeTab === 'quality' && <QualityProfilesTab />}
      {activeTab === 'automation' && <AutomationTab />}
    </div>
  )
}

// --- Reusable form components ---

function FieldInput({
  label,
  description,
  value,
  onChange,
  type = 'text',
  placeholder,
  secret,
}: {
  label: string
  description?: string
  value: string
  onChange: (v: string) => void
  type?: string
  placeholder?: string
  secret?: boolean
}) {
  const [show, setShow] = useState(false)

  return (
    <div className="space-y-1.5">
      <label className="block text-sm font-medium text-white">{label}</label>
      {description && (
        <p className="text-xs text-surface-400">{description}</p>
      )}
      <div className="relative">
        <input
          type={secret && !show ? 'password' : type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 text-sm text-white placeholder-surface-500 focus:outline-none focus:border-primary-500"
        />
        {secret && (
          <button
            type="button"
            onClick={() => setShow(!show)}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-surface-400 hover:text-white"
          >
            {show ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        )}
      </div>
    </div>
  )
}

function FieldSelect({
  label,
  description,
  value,
  onChange,
  options,
}: {
  label: string
  description?: string
  value: string
  onChange: (v: string) => void
  options: { value: string; label: string }[]
}) {
  return (
    <div className="space-y-1.5">
      <label className="block text-sm font-medium text-white">{label}</label>
      {description && (
        <p className="text-xs text-surface-400">{description}</p>
      )}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full bg-surface-800 border border-surface-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-primary-500"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  )
}

function FieldToggle({
  label,
  description,
  checked,
  onChange,
}: {
  label: string
  description?: string
  checked: boolean
  onChange: (v: boolean) => void
}) {
  return (
    <div className="flex items-center justify-between py-2">
      <div>
        <div className="text-sm font-medium text-white">{label}</div>
        {description && (
          <p className="text-xs text-surface-400">{description}</p>
        )}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={cn(
          'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
          checked ? 'bg-primary-500' : 'bg-surface-700'
        )}
      >
        <span
          className={cn(
            'inline-block h-4 w-4 rounded-full bg-white transition-transform',
            checked ? 'translate-x-6' : 'translate-x-1'
          )}
        />
      </button>
    </div>
  )
}

// --- Services Tab (editable) ---

function ServicesTab() {
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['general-settings'],
    queryFn: () => settingsApi.getGeneral(),
  })

  const { data: statusData, refetch: refetchStatus } = useQuery({
    queryKey: ['service-status'],
    queryFn: () => settingsApi.getServiceStatus(),
  })

  const saveMutation = useMutation({
    mutationFn: (settings: Record<string, string>) =>
      settingsApi.updateGeneral(settings),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['general-settings'] })
      queryClient.invalidateQueries({ queryKey: ['service-status'] })
      toast.success('Settings saved')
    },
    onError: () => toast.error('Failed to save settings'),
  })

  const testMutation = useMutation({
    mutationFn: (service: string) => settingsApi.testService(service),
    onSuccess: (res, service) => {
      const d = res.data as any
      if (d.connected || d.available) {
        toast.success(`${service} connection successful`)
      } else {
        toast.error(`${service} connection failed: ${d.reason || 'unknown error'}`)
      }
      refetchStatus()
    },
    onError: (_, service) => toast.error(`Failed to test ${service}`),
  })

  const [form, setForm] = useState<Record<string, string>>({})

  useEffect(() => {
    if (data?.data) {
      const s = data.data
      setForm({
        plex_url: s.plex_url,
        plex_token: s.plex_token,
        spotify_client_id: s.spotify_client_id,
        spotify_client_secret: s.spotify_client_secret,
        lastfm_api_key: s.lastfm_api_key,
        lastfm_shared_secret: s.lastfm_shared_secret,
        prowlarr_url: s.prowlarr_url,
        prowlarr_api_key: s.prowlarr_api_key,
        qbittorrent_url: s.qbittorrent_url,
        qbittorrent_username: s.qbittorrent_username,
        qbittorrent_password: s.qbittorrent_password,
        qbittorrent_category: s.qbittorrent_category,
        beets_enabled: String(s.beets_enabled),
        beets_config_path: s.beets_config_path,
        beets_library_path: s.beets_library_path,
        beets_auto_import: String(s.beets_auto_import),
        beets_move_files: String(s.beets_move_files),
        musicbrainz_user_agent: s.musicbrainz_user_agent,
      })
    }
  }, [data])

  const set = useCallback(
    (key: string, value: string) => setForm((prev) => ({ ...prev, [key]: value })),
    []
  )

  if (isLoading) return <LoadingPage message="Loading settings..." />

  const services = statusData?.data

  const handleSave = () => saveMutation.mutate(form)

  return (
    <div className="space-y-6">
      {/* Connection status */}
      <div className="card p-6">
        <h3 className="text-lg font-semibold text-white mb-4">
          Connection Status
        </h3>
        <div className="space-y-3">
          <ServiceRow
            name="Prowlarr"
            description="Indexer search aggregator"
            configured={services?.prowlarr?.configured || false}
            connected={services?.prowlarr?.connected || false}
            extra={undefined}
            reason={undefined}
          />
          <ServiceRow
            name="qBittorrent"
            description="Torrent download client"
            configured={services?.qbittorrent?.configured || false}
            connected={services?.qbittorrent?.connected || false}
            extra={services?.qbittorrent?.version ? `v${services.qbittorrent.version}` : undefined}
            reason={undefined}
          />
          <ServiceRow
            name="Beets"
            description="Music tagging and organization"
            configured={services?.beets?.available || false}
            connected={services?.beets?.available || false}
            extra={services?.beets?.version || undefined}
            reason={services?.beets?.reason}
          />
        </div>
        <button onClick={() => refetchStatus()} className="btn-secondary mt-4">
          <Shield className="w-4 h-4" />
          Refresh Status
        </button>
      </div>

      {/* Plex */}
      <div className="card p-6 space-y-4">
        <h3 className="text-lg font-semibold text-white">Plex</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <FieldInput label="Plex URL" value={form.plex_url || ''} onChange={(v) => set('plex_url', v)} placeholder="http://localhost:32400" />
          <FieldInput label="Plex Token" value={form.plex_token || ''} onChange={(v) => set('plex_token', v)} secret />
        </div>
      </div>

      {/* Spotify */}
      <div className="card p-6 space-y-4">
        <h3 className="text-lg font-semibold text-white">Spotify</h3>
        <p className="text-xs text-surface-400">Get credentials at developer.spotify.com/dashboard</p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <FieldInput label="Client ID" value={form.spotify_client_id || ''} onChange={(v) => set('spotify_client_id', v)} />
          <FieldInput label="Client Secret" value={form.spotify_client_secret || ''} onChange={(v) => set('spotify_client_secret', v)} secret />
        </div>
      </div>

      {/* Last.fm */}
      <div className="card p-6 space-y-4">
        <h3 className="text-lg font-semibold text-white">Last.fm</h3>
        <p className="text-xs text-surface-400">Get credentials at last.fm/api/account/create</p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <FieldInput label="API Key" value={form.lastfm_api_key || ''} onChange={(v) => set('lastfm_api_key', v)} secret />
          <FieldInput label="Shared Secret" value={form.lastfm_shared_secret || ''} onChange={(v) => set('lastfm_shared_secret', v)} secret />
        </div>
      </div>

      {/* Prowlarr */}
      <div className="card p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-white">Prowlarr</h3>
          <button
            onClick={() => testMutation.mutate('prowlarr')}
            className="btn-ghost text-xs"
            disabled={testMutation.isPending}
          >
            {testMutation.isPending ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Test'}
          </button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <FieldInput label="Prowlarr URL" value={form.prowlarr_url || ''} onChange={(v) => set('prowlarr_url', v)} placeholder="http://localhost:9696" />
          <FieldInput label="API Key" value={form.prowlarr_api_key || ''} onChange={(v) => set('prowlarr_api_key', v)} secret />
        </div>
      </div>

      {/* qBittorrent */}
      <div className="card p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-white">qBittorrent</h3>
          <button
            onClick={() => testMutation.mutate('qbittorrent')}
            className="btn-ghost text-xs"
            disabled={testMutation.isPending}
          >
            {testMutation.isPending ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Test'}
          </button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <FieldInput label="URL" value={form.qbittorrent_url || ''} onChange={(v) => set('qbittorrent_url', v)} placeholder="http://localhost:8080" />
          <FieldInput label="Username" value={form.qbittorrent_username || ''} onChange={(v) => set('qbittorrent_username', v)} placeholder="admin" />
          <FieldInput label="Password" value={form.qbittorrent_password || ''} onChange={(v) => set('qbittorrent_password', v)} secret />
          <FieldInput label="Category" value={form.qbittorrent_category || ''} onChange={(v) => set('qbittorrent_category', v)} placeholder="vibarr" />
        </div>
      </div>

      {/* Beets */}
      <div className="card p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-white">Beets</h3>
          <button
            onClick={() => testMutation.mutate('beets')}
            className="btn-ghost text-xs"
            disabled={testMutation.isPending}
          >
            {testMutation.isPending ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Test'}
          </button>
        </div>
        <FieldToggle label="Enable Beets" description="Automatically tag and organize completed downloads" checked={form.beets_enabled === 'true'} onChange={(v) => set('beets_enabled', String(v))} />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <FieldInput label="Config Path" value={form.beets_config_path || ''} onChange={(v) => set('beets_config_path', v)} placeholder="/config/beets/config.yaml" />
          <FieldInput label="Library Path" value={form.beets_library_path || ''} onChange={(v) => set('beets_library_path', v)} placeholder="/music" />
        </div>
        <FieldToggle label="Auto Import" description="Automatically import completed downloads" checked={form.beets_auto_import === 'true'} onChange={(v) => set('beets_auto_import', String(v))} />
        <FieldToggle label="Move Files" description="Move files instead of copying after import" checked={form.beets_move_files === 'true'} onChange={(v) => set('beets_move_files', String(v))} />
      </div>

      {/* MusicBrainz */}
      <div className="card p-6 space-y-4">
        <h3 className="text-lg font-semibold text-white">MusicBrainz</h3>
        <FieldInput label="User Agent" value={form.musicbrainz_user_agent || ''} onChange={(v) => set('musicbrainz_user_agent', v)} placeholder="Vibarr/1.0" />
      </div>

      {/* Save button */}
      <div className="flex justify-end">
        <button
          onClick={handleSave}
          disabled={saveMutation.isPending}
          className="btn-primary flex items-center gap-2"
        >
          {saveMutation.isPending ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Save className="w-4 h-4" />
          )}
          Save Settings
        </button>
      </div>
    </div>
  )
}

function ServiceRow({
  name,
  description,
  configured,
  connected,
  extra,
  reason,
}: {
  name: string
  description: string
  configured: boolean
  connected: boolean
  extra?: string
  reason?: string
}) {
  return (
    <div className="flex items-center justify-between p-4 bg-surface-800/50 rounded-lg">
      <div className="flex items-center gap-4">
        <div
          className={cn(
            'w-10 h-10 rounded-lg flex items-center justify-center',
            connected
              ? 'bg-green-500/20'
              : configured
                ? 'bg-yellow-500/20'
                : 'bg-surface-700'
          )}
        >
          {connected ? (
            <CheckCircle className="w-5 h-5 text-green-400" />
          ) : configured ? (
            <AlertCircle className="w-5 h-5 text-yellow-400" />
          ) : (
            <XCircle className="w-5 h-5 text-surface-500" />
          )}
        </div>
        <div>
          <div className="flex items-center gap-2">
            <span className="font-medium text-white">{name}</span>
            {extra && (
              <span className="text-xs text-surface-400">({extra})</span>
            )}
          </div>
          <div className="text-sm text-surface-400">{description}</div>
          {reason && !connected && (
            <div className="text-xs text-yellow-400 mt-1">{reason}</div>
          )}
        </div>
      </div>
      <div className="text-right">
        <span
          className={cn(
            'text-sm font-medium',
            connected
              ? 'text-green-400'
              : configured
                ? 'text-yellow-400'
                : 'text-surface-500'
          )}
        >
          {connected ? 'Connected' : configured ? 'Configured' : 'Not configured'}
        </span>
      </div>
    </div>
  )
}

// --- Quality Profiles Tab (unchanged) ---

function QualityProfilesTab() {
  const queryClient = useQueryClient()
  const [editingId, setEditingId] = useState<number | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['quality-profiles'],
    queryFn: () => settingsApi.getQualityProfiles(),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => settingsApi.deleteQualityProfile(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['quality-profiles'] })
      toast.success('Profile deleted')
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || 'Cannot delete profile')
    },
  })

  const setDefaultMutation = useMutation({
    mutationFn: (id: number) =>
      settingsApi.updateQualityProfile(id, { is_default: true }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['quality-profiles'] })
      toast.success('Default profile updated')
    },
  })

  if (isLoading) return <LoadingPage message="Loading profiles..." />

  const profiles = data?.data || []

  return (
    <div className="space-y-4">
      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-semibold text-white">
              Quality Profiles
            </h3>
            <p className="text-sm text-surface-400 mt-1">
              Define format and quality preferences for downloads. The default
              profile is used for auto-downloads.
            </p>
          </div>
        </div>

        <div className="space-y-3">
          {profiles.map((profile: QualityProfile) => (
            <div
              key={profile.id}
              className="p-4 bg-surface-800/50 rounded-lg"
            >
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-white">
                      {profile.name}
                    </span>
                    {profile.is_default && (
                      <span className="bg-primary-500/20 text-primary-400 text-xs px-2 py-0.5 rounded-full">
                        Default
                      </span>
                    )}
                  </div>
                  {profile.description && (
                    <p className="text-sm text-surface-400 mt-1">
                      {profile.description}
                    </p>
                  )}
                  <div className="flex items-center gap-3 mt-2 text-xs text-surface-400">
                    <span>
                      Formats:{' '}
                      {profile.preferred_formats.length > 0
                        ? profile.preferred_formats
                            .map((f) => f.toUpperCase())
                            .join(' > ')
                        : 'Any'}
                    </span>
                    <span>&middot;</span>
                    <span>
                      Min quality:{' '}
                      {profile.min_quality === 'any'
                        ? 'Any'
                        : profile.min_quality.toUpperCase()}
                    </span>
                    <span>&middot;</span>
                    <span>Min seeders: {profile.min_seeders}</span>
                    {profile.max_size_mb > 0 && (
                      <>
                        <span>&middot;</span>
                        <span>Max size: {profile.max_size_mb} MB</span>
                      </>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {!profile.is_default && (
                    <button
                      onClick={() => setDefaultMutation.mutate(profile.id)}
                      className="btn-ghost text-xs py-1 px-2"
                    >
                      Set Default
                    </button>
                  )}
                  {!profile.is_default && (
                    <button
                      onClick={() => deleteMutation.mutate(profile.id)}
                      className="btn-ghost p-2 text-red-400 hover:text-red-300"
                      title="Delete"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="card p-6">
        <h3 className="text-lg font-semibold text-white mb-2">
          Quality Priority
        </h3>
        <p className="text-sm text-surface-400 mb-4">
          When searching for releases, Vibarr scores results based on your
          quality profile. Higher-priority formats are preferred, and releases
          below minimum quality are rejected.
        </p>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div className="bg-surface-800/50 rounded-lg p-4">
            <div className="font-medium text-white mb-2">Format Hierarchy</div>
            <div className="space-y-1 text-surface-400">
              <div>FLAC 24-bit (Hi-Res)</div>
              <div>FLAC (Lossless)</div>
              <div>MP3 320kbps</div>
              <div>MP3 V0 (VBR ~245kbps)</div>
              <div>MP3 256kbps</div>
              <div>MP3 192kbps</div>
            </div>
          </div>
          <div className="bg-surface-800/50 rounded-lg p-4">
            <div className="font-medium text-white mb-2">Scoring Factors</div>
            <div className="space-y-1 text-surface-400">
              <div>Title match (artist + album)</div>
              <div>Format/quality preference</div>
              <div>Seeder count</div>
              <div>File size sanity check</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

// --- Automation Tab (editable) ---

function AutomationTab() {
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['general-settings'],
    queryFn: () => settingsApi.getGeneral(),
  })

  const saveMutation = useMutation({
    mutationFn: (settings: Record<string, string>) =>
      settingsApi.updateGeneral(settings),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['general-settings'] })
      toast.success('Settings saved')
    },
    onError: () => toast.error('Failed to save settings'),
  })

  const [form, setForm] = useState<Record<string, string>>({})

  useEffect(() => {
    if (data?.data) {
      const s = data.data
      setForm({
        auto_download_enabled: String(s.auto_download_enabled),
        auto_download_confidence_threshold: String(s.auto_download_confidence_threshold),
        preferred_quality: s.preferred_quality,
        max_concurrent_downloads: String(s.max_concurrent_downloads),
        download_path: s.download_path,
        completed_download_path: s.completed_download_path,
      })
    }
  }, [data])

  const set = useCallback(
    (key: string, value: string) => setForm((prev) => ({ ...prev, [key]: value })),
    []
  )

  if (isLoading) return <LoadingPage message="Loading settings..." />

  const handleSave = () => saveMutation.mutate(form)

  return (
    <div className="space-y-6">
      <div className="card p-6 space-y-4">
        <h3 className="text-lg font-semibold text-white">
          Download Automation
        </h3>
        <p className="text-sm text-surface-400">
          Configure how Vibarr automatically searches and downloads music from
          your wishlist.
        </p>

        <FieldToggle
          label="Auto-Download"
          description="Automatically download high-confidence matches from wishlist searches"
          checked={form.auto_download_enabled === 'true'}
          onChange={(v) => set('auto_download_enabled', String(v))}
        />

        <FieldInput
          label="Confidence Threshold"
          description="Minimum match score (0.0 - 1.0) required for auto-downloads"
          value={form.auto_download_confidence_threshold || '0.8'}
          onChange={(v) => set('auto_download_confidence_threshold', v)}
          type="number"
          placeholder="0.8"
        />

        <FieldSelect
          label="Preferred Quality"
          description="Default format preference when no quality profile is specified"
          value={form.preferred_quality || 'flac'}
          onChange={(v) => set('preferred_quality', v)}
          options={[
            { value: 'flac', label: 'FLAC (Lossless)' },
            { value: '320', label: 'MP3 320kbps' },
            { value: 'v0', label: 'MP3 V0 (VBR)' },
          ]}
        />

        <FieldInput
          label="Max Concurrent Downloads"
          description="Maximum number of simultaneous downloads"
          value={form.max_concurrent_downloads || '3'}
          onChange={(v) => set('max_concurrent_downloads', v)}
          type="number"
          placeholder="3"
        />

        <FieldInput
          label="Download Path"
          description="Directory where active downloads are stored"
          value={form.download_path || '/downloads'}
          onChange={(v) => set('download_path', v)}
          placeholder="/downloads"
        />

        <FieldInput
          label="Completed Path"
          description="Directory for completed downloads awaiting import"
          value={form.completed_download_path || '/downloads/completed'}
          onChange={(v) => set('completed_download_path', v)}
          placeholder="/downloads/completed"
        />
      </div>

      {/* Save button */}
      <div className="flex justify-end">
        <button
          onClick={handleSave}
          disabled={saveMutation.isPending}
          className="btn-primary flex items-center gap-2"
        >
          {saveMutation.isPending ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Save className="w-4 h-4" />
          )}
          Save Settings
        </button>
      </div>

      <div className="card p-6">
        <h3 className="text-lg font-semibold text-white mb-2">
          Automation Pipeline
        </h3>
        <p className="text-sm text-surface-400 mb-4">
          How the automated download pipeline works:
        </p>
        <div className="space-y-3">
          {[
            {
              step: '1',
              title: 'Wishlist Search',
              desc: 'Every hour, Vibarr searches Prowlarr for wanted items with auto-download enabled.',
            },
            {
              step: '2',
              title: 'Quality Matching',
              desc: 'Results are scored against your quality profile. Only matches above the confidence threshold proceed.',
            },
            {
              step: '3',
              title: 'Grab & Download',
              desc: 'The best matching release is sent to qBittorrent for downloading.',
            },
            {
              step: '4',
              title: 'Status Monitoring',
              desc: 'Every 5 minutes, download progress is checked and updated.',
            },
            {
              step: '5',
              title: 'Import (optional)',
              desc: 'When beets is enabled, completed downloads are automatically imported, tagged, and organized.',
            },
          ].map((item) => (
            <div
              key={item.step}
              className="flex items-start gap-3 p-3 bg-surface-800/50 rounded-lg"
            >
              <div className="w-6 h-6 bg-primary-500/20 text-primary-400 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0">
                {item.step}
              </div>
              <div>
                <div className="font-medium text-white text-sm">
                  {item.title}
                </div>
                <div className="text-xs text-surface-400">{item.desc}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
