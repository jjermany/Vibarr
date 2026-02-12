import { describe, expect, it } from 'vitest'
import type { Download } from '@/lib/api'
import { getVisibleSelectionState } from './selection'

const baseDownload: Download = {
  id: 1,
  artist_name: 'Artist',
  album_title: 'Album',
  status: 'queued',
  progress: 0,
  source: 'manual',
  beets_imported: false,
  created_at: new Date().toISOString(),
}

describe('getVisibleSelectionState', () => {
  it('returns no selection for empty list', () => {
    const state = getVisibleSelectionState([], new Set<number>())

    expect(state).toEqual({
      visibleCount: 0,
      selectedVisibleCount: 0,
      hasVisible: false,
      hasSelection: false,
      allVisibleSelected: false,
    })
  })

  it('tracks selected visible records only', () => {
    const downloads: Download[] = [
      { ...baseDownload, id: 10 },
      { ...baseDownload, id: 20 },
    ]

    const state = getVisibleSelectionState(downloads, new Set([20, 999]))

    expect(state).toEqual({
      visibleCount: 2,
      selectedVisibleCount: 1,
      hasVisible: true,
      hasSelection: true,
      allVisibleSelected: false,
    })
  })

  it('marks all visible selected when every visible id is selected', () => {
    const downloads: Download[] = [
      { ...baseDownload, id: 30 },
      { ...baseDownload, id: 40 },
    ]

    const state = getVisibleSelectionState(downloads, new Set([30, 40]))

    expect(state.allVisibleSelected).toBe(true)
    expect(state.selectedVisibleCount).toBe(2)
  })
})
