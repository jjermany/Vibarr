'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Zap,
  Plus,
  Settings2,
  Play,
  Pause,
  Trash2,
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  XCircle,
  Clock,
  AlertTriangle,
  BarChart3,
  FileText,
} from 'lucide-react'
import { automationApi } from '@/lib/api'
import type { AutomationRule, AutomationLog } from '@/lib/api'
import { cn, formatDate } from '@/lib/utils'
import toast from 'react-hot-toast'

const TRIGGER_LABELS: Record<string, { label: string; color: string }> = {
  new_release: { label: 'New Release', color: 'bg-green-500/20 text-green-400' },
  library_sync: { label: 'Library Sync', color: 'bg-blue-500/20 text-blue-400' },
  recommendation_generated: { label: 'Recommendation', color: 'bg-purple-500/20 text-purple-400' },
  listening_milestone: { label: 'Milestone', color: 'bg-yellow-500/20 text-yellow-400' },
  new_artist_discovered: { label: 'New Artist', color: 'bg-pink-500/20 text-pink-400' },
  schedule: { label: 'Scheduled', color: 'bg-cyan-500/20 text-cyan-400' },
  playlist_url_check: { label: 'Playlist URL', color: 'bg-orange-500/20 text-orange-400' },
}

export default function AutomationPage() {
  const [activeTab, setActiveTab] = useState<'rules' | 'create' | 'stats'>('rules')
  const [expandedRule, setExpandedRule] = useState<number | null>(null)
  const queryClient = useQueryClient()

  // Form state for creating rules
  const [newRule, setNewRule] = useState({
    name: '',
    description: '',
    trigger: 'new_release',
    conditions: [] as { field: string; operator: string; value: string }[],
    actions: [] as { type: string; params: Record<string, any> }[],
  })

  const { data: rules } = useQuery({
    queryKey: ['automation-rules'],
    queryFn: async () => {
      const res = await automationApi.listRules()
      return res.data
    },
  })

  const { data: triggers } = useQuery({
    queryKey: ['automation-triggers'],
    queryFn: async () => {
      const res = await automationApi.getTriggers()
      return res.data
    },
  })

  const { data: stats } = useQuery({
    queryKey: ['automation-stats'],
    queryFn: async () => {
      const res = await automationApi.getStats()
      return res.data
    },
  })

  const toggleMutation = useMutation({
    mutationFn: (id: number) => automationApi.toggleRule(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['automation-rules'] }),
    onError: (error: any) => {
      const detail = error?.response?.data?.detail
      toast.error(detail || 'Failed to toggle automation rule')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => automationApi.deleteRule(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['automation-rules'] })
      toast.success('Automation rule deleted')
    },
    onError: (error: any) => {
      const detail = error?.response?.data?.detail
      toast.error(detail || 'Failed to delete automation rule')
    },
  })

  const createMutation = useMutation({
    mutationFn: (data: any) => automationApi.createRule(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['automation-rules'] })
      setActiveTab('rules')
      setNewRule({ name: '', description: '', trigger: 'new_release', conditions: [], actions: [] })
      toast.success('Automation rule created')
    },
    onError: (error: any) => {
      const detail = error?.response?.data?.detail
      toast.error(detail || 'Failed to create automation rule')
    },
  })

  const tabs = [
    { key: 'rules' as const, label: 'Rules', icon: Zap },
    { key: 'create' as const, label: 'Create Rule', icon: Plus },
    { key: 'stats' as const, label: 'Statistics', icon: BarChart3 },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Automation Rules</h1>
        <p className="text-surface-400 mt-1">Define rules that automatically act on new releases, recommendations, and more</p>
      </div>

      {/* Stats overview */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="card p-3 text-center">
            <p className="text-2xl font-bold text-white">{stats.total_rules}</p>
            <p className="text-xs text-surface-400">Total Rules</p>
          </div>
          <div className="card p-3 text-center">
            <p className="text-2xl font-bold text-green-400">{stats.active_rules}</p>
            <p className="text-xs text-surface-400">Active</p>
          </div>
          <div className="card p-3 text-center">
            <p className="text-2xl font-bold text-blue-400">{stats.total_executions}</p>
            <p className="text-xs text-surface-400">Executions</p>
          </div>
          <div className="card p-3 text-center">
            <p className="text-2xl font-bold text-red-400">{stats.failed_executions}</p>
            <p className="text-xs text-surface-400">Failed</p>
          </div>
        </div>
      )}

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

      {/* Rules List */}
      {activeTab === 'rules' && (
        <div className="space-y-3">
          {rules && rules.length > 0 ? (
            rules.map((rule: AutomationRule) => {
              const isExpanded = expandedRule === rule.id
              const triggerInfo = TRIGGER_LABELS[rule.trigger] || { label: rule.trigger, color: 'bg-surface-700 text-surface-300' }

              return (
                <div key={rule.id} className="card overflow-hidden">
                  <div
                    className="p-4 flex items-center gap-3 cursor-pointer hover:bg-surface-800/50 transition-colors"
                    onClick={() => setExpandedRule(isExpanded ? null : rule.id)}
                  >
                    <div className={cn(
                      'w-2 h-2 rounded-full flex-shrink-0',
                      rule.is_enabled ? 'bg-green-400' : 'bg-surface-500'
                    )} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <h4 className="text-white font-semibold truncate">{rule.name}</h4>
                        <span className={cn('px-2 py-0.5 rounded text-xs font-medium', triggerInfo.color)}>
                          {triggerInfo.label}
                        </span>
                      </div>
                      {rule.description && (
                        <p className="text-surface-400 text-sm truncate mt-0.5">{rule.description}</p>
                      )}
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <span className="text-surface-500 text-xs">
                        {rule.trigger_count} runs
                      </span>
                      <button
                        onClick={(e) => { e.stopPropagation(); toggleMutation.mutate(rule.id) }}
                        className={cn(
                          'p-1.5 rounded transition-colors',
                          rule.is_enabled ? 'text-green-400 hover:bg-green-400/10' : 'text-surface-500 hover:bg-surface-700'
                        )}
                      >
                        {rule.is_enabled ? <Play className="w-4 h-4" /> : <Pause className="w-4 h-4" />}
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); deleteMutation.mutate(rule.id) }}
                        className="p-1.5 rounded text-surface-500 hover:text-red-400 hover:bg-red-400/10 transition-colors"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                      {isExpanded ? <ChevronDown className="w-4 h-4 text-surface-500" /> : <ChevronRight className="w-4 h-4 text-surface-500" />}
                    </div>
                  </div>

                  {/* Expanded details */}
                  {isExpanded && (
                    <div className="px-4 pb-4 pt-0 border-t border-surface-800 space-y-3">
                      {/* Conditions */}
                      <div>
                        <h5 className="text-xs font-semibold text-surface-400 uppercase tracking-wide mb-2">Conditions</h5>
                        {rule.conditions.length > 0 ? (
                          <div className="space-y-1">
                            {rule.conditions.map((cond, i) => (
                              <div key={i} className="text-sm text-surface-300 bg-surface-800 rounded px-3 py-1.5">
                                <span className="text-primary-400">{cond.field}</span>
                                {' '}<span className="text-surface-500">{cond.operator}</span>{' '}
                                <span className="text-white">{JSON.stringify(cond.value)}</span>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p className="text-surface-500 text-sm">No conditions (always matches)</p>
                        )}
                      </div>

                      {/* Actions */}
                      <div>
                        <h5 className="text-xs font-semibold text-surface-400 uppercase tracking-wide mb-2">Actions</h5>
                        {rule.actions.length > 0 ? (
                          <div className="space-y-1">
                            {rule.actions.map((action, i) => (
                              <div key={i} className="text-sm text-surface-300 bg-surface-800 rounded px-3 py-1.5">
                                <span className="text-accent-400">{action.type.replace(/_/g, ' ')}</span>
                                {Object.keys(action.params || {}).length > 0 && (
                                  <span className="text-surface-500"> ({JSON.stringify(action.params)})</span>
                                )}
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p className="text-surface-500 text-sm">No actions defined</p>
                        )}
                      </div>

                      {/* Metadata */}
                      <div className="flex items-center gap-4 text-xs text-surface-500">
                        {rule.last_triggered_at && (
                          <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3" /> Last run: {formatDate(rule.last_triggered_at)}
                          </span>
                        )}
                        {rule.last_error && (
                          <span className="flex items-center gap-1 text-red-400">
                            <AlertTriangle className="w-3 h-3" /> {rule.last_error}
                          </span>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )
            })
          ) : (
            <div className="text-center py-12">
              <Zap className="w-12 h-12 text-surface-500 mx-auto mb-3" />
              <h3 className="text-lg font-semibold text-white">No Automation Rules</h3>
              <p className="text-surface-400 mt-1 max-w-md mx-auto">
                Create rules to automatically add releases to your wishlist, start downloads,
                tag items, and more based on your preferences.
              </p>
              <button
                onClick={() => setActiveTab('create')}
                className="btn btn-primary mt-4"
              >
                <Plus className="w-4 h-4 mr-2" /> Create Your First Rule
              </button>
            </div>
          )}
        </div>
      )}

      {/* Create Rule */}
      {activeTab === 'create' && (
        <div className="card p-6 space-y-6">
          <h3 className="text-lg font-semibold text-white">Create Automation Rule</h3>

          {/* Name */}
          <div>
            <label className="block text-sm text-surface-300 mb-1">Rule Name</label>
            <input
              type="text"
              placeholder="e.g., Auto-download new rock releases"
              value={newRule.name}
              onChange={(e) => setNewRule({ ...newRule, name: e.target.value })}
              className="input w-full"
            />
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm text-surface-300 mb-1">Description</label>
            <input
              type="text"
              placeholder="What does this rule do?"
              value={newRule.description}
              onChange={(e) => setNewRule({ ...newRule, description: e.target.value })}
              className="input w-full"
            />
          </div>

          {/* Trigger */}
          <div>
            <label className="block text-sm text-surface-300 mb-1">Trigger</label>
            <select
              value={newRule.trigger}
              onChange={(e) => setNewRule({ ...newRule, trigger: e.target.value })}
              className="input w-full"
            >
              {triggers?.triggers?.map((t: any) => (
                <option key={t.value} value={t.value}>{t.label} - {t.description}</option>
              )) || (
                <>
                  <option value="new_release">New Release</option>
                  <option value="library_sync">Library Sync</option>
                  <option value="recommendation_generated">Recommendation Generated</option>
                  <option value="listening_milestone">Listening Milestone</option>
                  <option value="new_artist_discovered">New Artist Discovered</option>
                  <option value="schedule">Scheduled</option>
                </>
              )}
            </select>
          </div>

          {/* Conditions */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm text-surface-300">Conditions (all must match)</label>
              <button
                onClick={() => setNewRule({
                  ...newRule,
                  conditions: [...newRule.conditions, { field: 'genre', operator: 'contains', value: '' }],
                })}
                className="btn btn-ghost text-xs"
              >
                <Plus className="w-3 h-3 mr-1" /> Add Condition
              </button>
            </div>
            {newRule.conditions.map((cond, i) => (
              <div key={i} className="flex gap-2 mb-2">
                <select
                  value={cond.field}
                  onChange={(e) => {
                    const updated = [...newRule.conditions]
                    updated[i] = { ...cond, field: e.target.value }
                    setNewRule({ ...newRule, conditions: updated })
                  }}
                  className="input flex-1"
                >
                  {(triggers?.condition_fields || [
                    'genre', 'artist_name', 'album_type', 'release_year', 'confidence_score',
                    'audio_energy', 'audio_danceability', 'audio_valence', 'popularity', 'format',
                  ]).map((f: string) => (
                    <option key={f} value={f}>{f.replace(/_/g, ' ')}</option>
                  ))}
                </select>
                <select
                  value={cond.operator}
                  onChange={(e) => {
                    const updated = [...newRule.conditions]
                    updated[i] = { ...cond, operator: e.target.value }
                    setNewRule({ ...newRule, conditions: updated })
                  }}
                  className="input w-40"
                >
                  <option value="contains">contains</option>
                  <option value="equals">equals</option>
                  <option value="not_equals">not equals</option>
                  <option value="greater_than">greater than</option>
                  <option value="less_than">less than</option>
                  <option value="in_list">in list</option>
                </select>
                <input
                  type="text"
                  value={cond.value}
                  onChange={(e) => {
                    const updated = [...newRule.conditions]
                    updated[i] = { ...cond, value: e.target.value }
                    setNewRule({ ...newRule, conditions: updated })
                  }}
                  placeholder="Value"
                  className="input flex-1"
                />
                <button
                  onClick={() => {
                    const updated = newRule.conditions.filter((_, idx) => idx !== i)
                    setNewRule({ ...newRule, conditions: updated })
                  }}
                  className="p-2 text-surface-500 hover:text-red-400"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>

          {/* Actions */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm text-surface-300">Actions (executed in order)</label>
              <button
                onClick={() => setNewRule({
                  ...newRule,
                  actions: [...newRule.actions, { type: 'add_to_wishlist', params: {} }],
                })}
                className="btn btn-ghost text-xs"
              >
                <Plus className="w-3 h-3 mr-1" /> Add Action
              </button>
            </div>
            {newRule.actions.map((action, i) => (
              <div key={i} className="space-y-2 mb-2">
                <div className="flex gap-2">
                  <select
                    value={action.type}
                    onChange={(e) => {
                      const updated = [...newRule.actions]
                      updated[i] = { type: e.target.value, params: {} }
                      setNewRule({ ...newRule, actions: updated })
                    }}
                    className="input flex-1"
                  >
                    {(triggers?.action_types || [
                      { value: 'add_to_wishlist', label: 'Add to Wishlist' },
                      { value: 'start_download', label: 'Start Download' },
                      { value: 'send_notification', label: 'Send Notification' },
                      { value: 'tag_item', label: 'Tag Item' },
                      { value: 'skip_item', label: 'Skip Item' },
                      { value: 'add_to_library', label: 'Add to Library' },
                      { value: 'import_playlist_url', label: 'Import from Playlist URL' },
                    ]).map((a: any) => (
                      <option key={a.value} value={a.value}>{a.label}</option>
                    ))}
                  </select>
                  <button
                    onClick={() => {
                      const updated = newRule.actions.filter((_, idx) => idx !== i)
                      setNewRule({ ...newRule, actions: updated })
                    }}
                    className="p-2 text-surface-500 hover:text-red-400"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
                {action.type === 'import_playlist_url' && (
                  <div className="flex gap-2 pl-2">
                    <input
                      type="text"
                      placeholder="Playlist URL (Deezer or YouTube)"
                      value={action.params?.url || ''}
                      onChange={(e) => {
                        const updated = [...newRule.actions]
                        updated[i] = { ...action, params: { ...action.params, url: e.target.value } }
                        setNewRule({ ...newRule, actions: updated })
                      }}
                      className="input flex-1"
                    />
                    <select
                      value={action.params?.priority || 'normal'}
                      onChange={(e) => {
                        const updated = [...newRule.actions]
                        updated[i] = { ...action, params: { ...action.params, priority: e.target.value } }
                        setNewRule({ ...newRule, actions: updated })
                      }}
                      className="input w-32"
                    >
                      <option value="low">Low</option>
                      <option value="normal">Normal</option>
                      <option value="high">High</option>
                    </select>
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Submit */}
          <div className="flex gap-3">
            <button
              onClick={() => createMutation.mutate(newRule)}
              disabled={!newRule.name || newRule.actions.length === 0 || createMutation.isPending}
              className="btn btn-primary"
            >
              Create Rule
            </button>
            <button
              onClick={() => setActiveTab('rules')}
              className="btn btn-ghost"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Stats */}
      {activeTab === 'stats' && stats && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="card p-6">
              <h4 className="text-surface-400 text-sm font-medium">Success Rate</h4>
              <p className="text-3xl font-bold text-white mt-1">
                {stats.total_executions > 0
                  ? Math.round((stats.successful_executions / stats.total_executions) * 100)
                  : 0}%
              </p>
              <div className="w-full bg-surface-700 rounded-full h-2 mt-3">
                <div
                  className="bg-green-400 rounded-full h-2 transition-all"
                  style={{
                    width: `${stats.total_executions > 0
                      ? (stats.successful_executions / stats.total_executions) * 100
                      : 0}%`
                  }}
                />
              </div>
            </div>
            <div className="card p-6">
              <h4 className="text-surface-400 text-sm font-medium">Rule Coverage</h4>
              <p className="text-3xl font-bold text-white mt-1">
                {stats.active_rules}/{stats.total_rules}
              </p>
              <p className="text-surface-400 text-sm mt-1">rules currently active</p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
