import type { Role } from '@/services/auth'

export type Page<T> = {
  items: T[]
  total: number
  page: number
  pageSize: number
}

export type Priority = 'low' | 'medium' | 'high' | 'critical'

export const priorityLabels: Record<Priority, string> = {
  low: 'Baixa',
  medium: 'Média',
  high: 'Alta',
  critical: 'Crítica',
}

export type UserSummary = {
  id: string
  name: string
  email: string
  role: Role
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  const date = value.length === 10 ? new Date(`${value}T00:00:00Z`) : new Date(value)
  return date.toLocaleDateString('pt-PT', { timeZone: 'UTC' })
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  return new Date(value).toLocaleString('pt-PT')
}
