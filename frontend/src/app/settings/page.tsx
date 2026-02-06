'use client'

import { useState } from 'react'
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
} from 'lucide-react'
import {
  settingsApi,
  type QualityProfile,
  type ServiceStatus,
  type DownloadSettings,
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
          Configure download automation, quality preferences, and integrations
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

function ServicesTab() {
  const { data, isLoading, refetch } = useQuery({
    queryKey: ['service-status'],
    queryFn: () => settingsApi.getServiceStatus(),
  })

  if (isLoading) return <LoadingPage message="Checking services..." />

  const services = data?.data

  return (
    <div className="space-y-4">
      <div className="card p-6">
        <h3 className="text-lg font-semibold text-white mb-4">
          Service Connections
        </h3>
        <p className="text-sm text-surface-400 mb-6">
          Status of external services used for the download pipeline.
        </p>

        <div className="space-y-4">
          {/* Prowlarr */}
          <ServiceRow
            name="Prowlarr"
            description="Indexer search aggregator"
            configured={services?.prowlarr?.configured || false}
            connected={services?.prowlarr?.connected || false}
            envVars={['PROWLARR_URL', 'PROWLARR_API_KEY']}
          />

          {/* qBittorrent */}
          <ServiceRow
            name="qBittorrent"
            description="Torrent download client"
            configured={services?.qbittorrent?.configured || false}
            connected={services?.qbittorrent?.connected || false}
            envVars={[
              'QBITTORRENT_URL',
              'QBITTORRENT_USERNAME',
              'QBITTORRENT_PASSWORD',
            ]}
            extra={
              services?.qbittorrent?.version
                ? `v${services.qbittorrent.version}`
                : undefined
            }
          />

          {/* Beets */}
          <ServiceRow
            name="Beets"
            description="Music tagging and organization"
            configured={services?.beets?.available || false}
            connected={services?.beets?.available || false}
            envVars={['BEETS_ENABLED', 'BEETS_CONFIG_PATH']}
            extra={services?.beets?.version || undefined}
            reason={services?.beets?.reason}
          />
        </div>

        <button
          onClick={() => refetch()}
          className="btn-secondary mt-6"
        >
          <Shield className="w-4 h-4" />
          Refresh Status
        </button>
      </div>

      <div className="card p-6">
        <h3 className="text-lg font-semibold text-white mb-2">
          Configuration
        </h3>
        <p className="text-sm text-surface-400 mb-4">
          Service connections are configured via environment variables in your{' '}
          <code className="text-primary-400">.env</code> file or Docker
          Compose configuration.
        </p>
        <div className="bg-surface-800 rounded-lg p-4 text-sm font-mono text-surface-300 overflow-x-auto">
          <pre>{`# Download Client (qBittorrent)
QBITTORRENT_URL=http://your-qbittorrent:8080
QBITTORRENT_USERNAME=admin
QBITTORRENT_PASSWORD=your_password

# Post-Processing (Beets)
BEETS_ENABLED=true
BEETS_LIBRARY_PATH=/music
BEETS_AUTO_IMPORT=true`}</pre>
        </div>
      </div>
    </div>
  )
}

function ServiceRow({
  name,
  description,
  configured,
  connected,
  envVars,
  extra,
  reason,
}: {
  name: string
  description: string
  configured: boolean
  connected: boolean
  envVars: string[]
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

function AutomationTab() {
  const { data, isLoading } = useQuery({
    queryKey: ['download-settings'],
    queryFn: () => settingsApi.getDownloadSettings(),
  })

  if (isLoading) return <LoadingPage message="Loading settings..." />

  const settings = data?.data

  return (
    <div className="space-y-4">
      <div className="card p-6">
        <h3 className="text-lg font-semibold text-white mb-4">
          Download Automation
        </h3>
        <p className="text-sm text-surface-400 mb-6">
          Configure how Vibarr automatically searches and downloads music from
          your wishlist.
        </p>

        <div className="space-y-6">
          {/* Auto Download Toggle */}
          <SettingRow
            label="Auto-Download"
            description="Automatically download high-confidence matches from wishlist searches"
            value={settings?.auto_download_enabled ? 'Enabled' : 'Disabled'}
            envVar="AUTO_DOWNLOAD_ENABLED"
          />

          {/* Confidence Threshold */}
          <SettingRow
            label="Confidence Threshold"
            description="Minimum match score (0-1) required for auto-downloads"
            value={`${((settings?.auto_download_confidence_threshold || 0.8) * 100).toFixed(0)}%`}
            envVar="AUTO_DOWNLOAD_CONFIDENCE_THRESHOLD"
          />

          {/* Preferred Quality */}
          <SettingRow
            label="Preferred Quality"
            description="Default format preference when no quality profile is specified"
            value={(settings?.preferred_quality || 'flac').toUpperCase()}
            envVar="PREFERRED_QUALITY"
          />

          {/* Concurrent Downloads */}
          <SettingRow
            label="Max Concurrent Downloads"
            description="Maximum number of simultaneous downloads"
            value={String(settings?.max_concurrent_downloads || 3)}
            envVar="MAX_CONCURRENT_DOWNLOADS"
          />

          {/* Download Path */}
          <SettingRow
            label="Download Path"
            description="Directory where active downloads are stored"
            value={settings?.download_path || '/downloads'}
            envVar="DOWNLOAD_PATH"
          />

          {/* Completed Path */}
          <SettingRow
            label="Completed Path"
            description="Directory for completed downloads awaiting import"
            value={settings?.completed_download_path || '/downloads/completed'}
            envVar="COMPLETED_DOWNLOAD_PATH"
          />
        </div>
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

      <div className="card p-6">
        <h3 className="text-lg font-semibold text-white mb-2">
          Configuration
        </h3>
        <p className="text-sm text-surface-400 mb-4">
          Automation settings are configured via environment variables. Update
          your <code className="text-primary-400">.env</code> file and restart
          containers to apply changes.
        </p>
        <div className="bg-surface-800 rounded-lg p-4 text-sm font-mono text-surface-300 overflow-x-auto">
          <pre>{`# Enable the full automation pipeline
AUTO_DOWNLOAD_ENABLED=true
AUTO_DOWNLOAD_CONFIDENCE_THRESHOLD=0.8
PREFERRED_QUALITY=flac
MAX_CONCURRENT_DOWNLOADS=3

# Post-processing with beets
BEETS_ENABLED=true
BEETS_AUTO_IMPORT=true
BEETS_MOVE_FILES=true`}</pre>
        </div>
      </div>
    </div>
  )
}

function SettingRow({
  label,
  description,
  value,
  envVar,
}: {
  label: string
  description: string
  value: string
  envVar: string
}) {
  return (
    <div className="flex items-center justify-between py-3 border-b border-surface-800 last:border-0">
      <div>
        <div className="font-medium text-white">{label}</div>
        <div className="text-sm text-surface-400">{description}</div>
      </div>
      <div className="text-right">
        <div className="font-medium text-white">{value}</div>
        <div className="text-xs text-surface-500 font-mono">{envVar}</div>
      </div>
    </div>
  )
}
