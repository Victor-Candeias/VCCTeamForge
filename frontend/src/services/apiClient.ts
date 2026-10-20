export type FieldError = { loc: (string | number)[]; msg: string; type?: string }

/** Campos adicionais de `application/problem+json` (ex.: `field`, `currentVersion`, `errors`). */
export type ProblemExtensions = {
  field?: string
  currentVersion?: number
  errors?: FieldError[]
  [key: string]: unknown
}

export class ApiError extends Error {
  readonly status: number
  readonly detail?: string
  readonly extensions: ProblemExtensions

  constructor(status: number, title: string, detail?: string, extensions: ProblemExtensions = {}) {
    super(detail ?? title)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
    this.extensions = extensions
  }

  get isConflict() {
    return this.status === 409
  }

  /** Mensagens de validação indexadas pelo nome do campo (último elemento de `loc`). */
  fieldErrors(): Record<string, string> {
    const result: Record<string, string> = {}
    if (this.extensions.field) result[this.extensions.field] = this.message
    for (const error of this.extensions.errors ?? []) {
      const name = error.loc.at(-1)
      if (typeof name === 'string') result[name] = error.msg
    }
    return result
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
  const isFormData = typeof FormData !== 'undefined' && init.body instanceof FormData
  if (init.body !== undefined && !isFormData && !headers.has('Content-Type')) {
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
    const { title, detail, ...extensions } = (await response.json()) as {
      title?: string
      detail?: string
    } & ProblemExtensions
    return new ApiError(response.status, title ?? response.statusText, detail, extensions)
  } catch {
    return new ApiError(response.status, response.statusText || 'Erro de comunicação')
  }
}

/** Constrói uma query string ignorando valores vazios; arrays repetem a chave. */
export function toQueryString(params: Record<string, unknown>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '' || value === false) continue
    if (Array.isArray(value)) {
      for (const item of value) search.append(key, String(item))
    } else {
      search.set(key, String(value))
    }
  }
  const query = search.toString()
  return query ? `?${query}` : ''
}
