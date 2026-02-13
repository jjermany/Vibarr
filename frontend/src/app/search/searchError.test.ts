import { describe, expect, it } from 'vitest'
import { getSearchErrorDetails } from './searchError'

describe('getSearchErrorDetails', () => {
  it('classifies timeout/network failures as network errors', () => {
    const timeoutError = {
      code: 'ECONNABORTED',
      response: { status: 504, data: { detail: 'Gateway timeout' } },
    }

    expect(getSearchErrorDetails(timeoutError)).toEqual({
      kind: 'network',
      detail: 'Gateway timeout',
    })
  })

  it('classifies auth errors', () => {
    const authError = {
      response: { status: 401, data: { detail: 'Unauthorized' } },
    }

    expect(getSearchErrorDetails(authError)).toEqual({
      kind: 'auth',
      detail: 'Unauthorized',
    })
  })

  it('classifies validation errors', () => {
    const validationError = {
      response: { status: 422, data: { detail: 'Invalid query' } },
    }

    expect(getSearchErrorDetails(validationError)).toEqual({
      kind: 'validation',
      detail: 'Invalid query',
    })
  })

  it('falls back to generic errors', () => {
    const genericError = new Error('Unexpected failure')

    expect(getSearchErrorDetails(genericError)).toEqual({
      kind: 'generic',
      detail: undefined,
    })
  })
})
