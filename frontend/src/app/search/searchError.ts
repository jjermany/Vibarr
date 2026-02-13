type SearchErrorKind = 'network' | 'auth' | 'validation' | 'generic'

type SearchErrorLike = {
  code?: string
  message?: string
  response?: {
    status?: number
    data?: {
      detail?: string
      message?: string
    }
  }
}

export type SearchErrorDetails = {
  kind: SearchErrorKind
  detail?: string
}

export function getSearchErrorDetails(error: unknown): SearchErrorDetails {
  const knownError = error as SearchErrorLike | null | undefined
  const status = knownError?.response?.status
  const code = knownError?.code
  const message = knownError?.message?.toLowerCase() || ''
  const detail = knownError?.response?.data?.detail || knownError?.response?.data?.message

  if (status === 401 || status === 403) {
    return { kind: 'auth', detail }
  }

  if (status === 400 || status === 422) {
    return { kind: 'validation', detail }
  }

  if (
    code === 'ECONNABORTED' ||
    message.includes('timeout') ||
    message.includes('network') ||
    status === 502 ||
    status === 503 ||
    status === 504
  ) {
    return { kind: 'network', detail }
  }

  return { kind: 'generic', detail }
}

