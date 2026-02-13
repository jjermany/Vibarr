import { describe, expect, it } from 'vitest'
import { isApiUsable } from './useBackendReadiness'

describe('isApiUsable', () => {
  it('returns true when backend status is ready', () => {
    expect(isApiUsable('ready', { database: false })).toBe(true)
  })

  it('returns true when database is ready even if redis-backed readiness is not ready', () => {
    expect(isApiUsable('starting', { database: true })).toBe(true)
  })

  it('returns false when neither status ready nor database check passes', () => {
    expect(isApiUsable('starting', { database: false })).toBe(false)
  })
})
