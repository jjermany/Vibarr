import type { WishlistItem } from '@/lib/api'

export function getVisibleSelectionState(items: WishlistItem[], selectedIds: Set<number>) {
  if (items.length === 0) {
    return { allVisibleSelected: false, someVisibleSelected: false, selectedVisibleCount: 0 }
  }

  const selectedVisibleCount = items.filter((item) => selectedIds.has(item.id)).length

  return {
    allVisibleSelected: selectedVisibleCount === items.length,
    someVisibleSelected: selectedVisibleCount > 0 && selectedVisibleCount < items.length,
    selectedVisibleCount,
  }
}

export function canSearchItem(item: WishlistItem) {
  return item.status === 'wanted'
}

export function getSearchableSelectedIds(items: WishlistItem[], selectedIds: Set<number>) {
  return items
    .filter((item) => selectedIds.has(item.id) && canSearchItem(item))
    .map((item) => item.id)
}
