export class ApiError extends Error {
  readonly status: number
  readonly detail?: string

  constructor(status: number, title: string, detail?: string) {
    super(detail ?? title)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

const API_BASE = '/api'
const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS'])
export const CSRF_COOKIE = 'vcctf_csrf'
export const CSRF_HEADER = 'X-CSRF-Token'

export function readCookie(name: string): string | undefined {
  const prefix = `${name}=`
  const entry = document.cookie.split('; ').find((cookie) => cookie.startsWith(prefix))
  return entry ? decodeURIComponent(entry.slice(prefix.length)) : undefined
}

async function ensureCsrfToken(): Promise<string> {
  const existing = readCookie(CSRF_COOKIE)
  if (existing) return existing
  const { csrfToken } = await apiFetch<{ csrfToken: string }>('/auth/csrf')
  return readCookie(CSRF_COOKIE) ?? csrfToken
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set('Accept', 'application/json')
  if (init.body !== undefined && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const method = (init.method ?? 'GET').toUpperCase()
  if (!SAFE_METHODS.has(method)) {
    // O backend exige o token CSRF (cookie + cabeçalho) em todos os métodos não seguros.
    headers.set(CSRF_HEADER, await ensureCsrfToken())
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    credentials: 'same-origin',
  })

  if (!response.ok) {
    throw await toApiError(response)
  }
  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

async function toApiError(response: Response): Promise<ApiError> {
  try {
    const body = (await response.json()) as { title?: string; detail?: string }
    return new ApiError(response.status, body.title ?? response.statusText, body.detail)
  } catch {
    return new ApiError(response.status, response.statusText || 'Erro de comunicação')
  }
}
