import { apiFetch } from '@/services/apiClient'

export type Health = {
  status: 'ok' | 'degraded' | 'error'
  version: string
}

export function getHealth() {
  return apiFetch<Health>('/health')
}
