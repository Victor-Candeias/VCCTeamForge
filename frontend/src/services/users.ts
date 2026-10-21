import { apiFetch, toQueryString } from '@/services/apiClient'
import type { Role } from '@/services/auth'
import type { Page } from '@/services/common'

export type UserStatus = 'active' | 'disabled'

export const userStatusLabels: Record<UserStatus, string> = {
  active: 'Ativo',
  disabled: 'Desativado',
}

export type ManagedUser = {
  id: string
  email: string
  name: string
  role: Role
  status: UserStatus
  lastLoginAt: string | null
  passwordChangedAt: string | null
  createdAt: string
  updatedAt: string
  version: number
}

export type UserFilters = {
  q?: string
  role?: Role[]
  status?: UserStatus[]
  sort?: string
  page?: number
  pageSize?: number
}

export type UserCreateInput = { email: string; name: string; role: Role; password: string }

export type UserUpdateInput = {
  version: number
  email?: string
  name?: string
  role?: Role
  status?: UserStatus
}

export function listUsers(filters: UserFilters = {}) {
  return apiFetch<Page<ManagedUser>>(`/admin/users${toQueryString(filters)}`)
}

export function getUser(userId: string) {
  return apiFetch<ManagedUser>(`/admin/users/${userId}`)
}

export function createUser(input: UserCreateInput) {
  return apiFetch<ManagedUser>('/admin/users', { method: 'POST', body: JSON.stringify(input) })
}

export function updateUser(userId: string, input: UserUpdateInput) {
  return apiFetch<ManagedUser>(`/admin/users/${userId}`, {
    method: 'PATCH',
    body: JSON.stringify(input),
  })
}

export function resetUserPassword(userId: string, input: { version: number; password: string }) {
  return apiFetch<ManagedUser>(`/admin/users/${userId}/password`, {
    method: 'POST',
    body: JSON.stringify(input),
  })
}
