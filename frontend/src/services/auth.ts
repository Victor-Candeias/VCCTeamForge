import { ApiError, apiFetch } from '@/services/apiClient'

export type Role = 'admin' | 'tech_lead' | 'developer' | 'qa'

export type CurrentUser = {
  id: string
  email: string
  name: string
  role: Role
  permissions: string[]
}

export const currentUserQueryKey = ['auth', 'me'] as const

export const roleLabels: Record<Role, string> = {
  admin: 'Administrador',
  tech_lead: 'Tech Lead',
  developer: 'Developer',
  qa: 'QA',
}

/** Devolve o utilizador autenticado, ou `null` se não houver sessão válida. */
export async function getCurrentUser(): Promise<CurrentUser | null> {
  try {
    return await apiFetch<CurrentUser>('/users/me')
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null
    throw error
  }
}

export function login(credentials: { email: string; password: string }) {
  return apiFetch<CurrentUser>('/auth/login', {
    method: 'POST',
    body: JSON.stringify(credentials),
  })
}

export function logout() {
  return apiFetch<void>('/auth/logout', { method: 'POST' })
}
