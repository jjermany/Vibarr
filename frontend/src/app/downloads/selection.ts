import type { Download } from '@/lib/api'

export function getVisibleSelectionState(downloads: Download[], selectedIds: Set<number>) {
  const visibleIds = downloads.map((download) => download.id)
  const selectedVisibleCount = visibleIds.filter((id) => selectedIds.has(id)).length

  return {
    visibleCount: visibleIds.length,
    selectedVisibleCount,
    hasVisible: visibleIds.length > 0,
    hasSelection: selectedVisibleCount > 0,
    allVisibleSelected: visibleIds.length > 0 && selectedVisibleCount === visibleIds.length,
  }
}
