import { apiFetch, toQueryString } from '@/services/apiClient'
import type { Page, UserSummary } from '@/services/common'

export type AuditLog = {
  id: string
  action: string
  actor: UserSummary | null
  entityType: string | null
  entityId: string | null
  ip: string | null
  requestId: string | null
  details: Record<string, unknown>
  createdAt: string
}

export type AuditFilters = {
  action?: string
  entityType?: string
  entityId?: string
  actorId?: string
  from?: string
  to?: string
  page?: number
  pageSize?: number
}

export function listAuditLogs(filters: AuditFilters) {
  return apiFetch<Page<AuditLog>>(`/audit-logs${toQueryString(filters)}`)
}
