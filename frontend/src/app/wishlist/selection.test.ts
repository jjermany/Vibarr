import { describe, expect, it } from 'vitest'
import { getVisibleSelectionState, getSearchableSelectedIds } from './selection'
import type { WishlistItem } from '@/lib/api'

const makeItem = (id: number, status: WishlistItem['status']): WishlistItem => ({
  id,
  item_type: 'album',
  artist_name: `Artist ${id}`,
  album_title: `Album ${id}`,
  status,
  priority: 'normal',
  source: 'manual',
  auto_download: false,
  created_at: new Date().toISOString(),
})

describe('wishlist selection helpers', () => {
  it('computes visible selection state for partial and full selection', () => {
    const items = [makeItem(1, 'wanted'), makeItem(2, 'found'), makeItem(3, 'wanted')]

    expect(getVisibleSelectionState(items, new Set([1]))).toEqual({
      allVisibleSelected: false,
      someVisibleSelected: true,
      selectedVisibleCount: 1,
    })

    expect(getVisibleSelectionState(items, new Set([1, 2, 3]))).toEqual({
      allVisibleSelected: true,
      someVisibleSelected: false,
      selectedVisibleCount: 3,
    })
  })

  it('only allows wanted selected IDs for bulk search', () => {
    const items = [makeItem(1, 'wanted'), makeItem(2, 'searching'), makeItem(3, 'failed')]

    expect(getSearchableSelectedIds(items, new Set([1, 2, 3]))).toEqual([1])
  })
})
