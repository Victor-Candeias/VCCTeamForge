import { apiFetch, toQueryString } from '@/services/apiClient'
import type { Page, Priority, UserSummary } from '@/services/common'

export type ProjectStatus = 'active' | 'on_hold' | 'completed' | 'archived'
export type EditableProjectStatus = Exclude<ProjectStatus, 'archived'>

export const projectStatusLabels: Record<ProjectStatus, string> = {
  active: 'Ativo',
  on_hold: 'Em pausa',
  completed: 'Concluído',
  archived: 'Arquivado',
}

export type ProjectSettings = {
  methodology: string
  sprintDurationDays: number
  estimationType: string
}

export type Project = {
  id: string
  key: string
  name: string
  description: string
  status: ProjectStatus
  priority: Priority
  lead: UserSummary | null
  startDate: string | null
  targetDate: string | null
  memberCount: number
  settings: ProjectSettings
  createdAt: string
  updatedAt: string
  archivedAt: string | null
  version: number
  canManage: boolean
}

export type ProjectMember = UserSummary & { isLead: boolean }

export type ProjectMembers = {
  version: number
  canManage: boolean
  members: ProjectMember[]
}

export type ProjectFilters = {
  q?: string
  status?: ProjectStatus[]
  includeArchived?: boolean
  sort?: string
  page?: number
  pageSize?: number
}

export type ProjectInput = {
  key?: string
  name: string
  description: string
  status: EditableProjectStatus
  priority: Priority
  leadUserId: string | null
  startDate: string | null
  targetDate: string | null
  settings?: { sprintDurationDays: number }
}

export function listProjects(filters: ProjectFilters = {}) {
  return apiFetch<Page<Project>>(`/projects${toQueryString(filters)}`)
}

export function getProject(projectId: string) {
  return apiFetch<Project>(`/projects/${projectId}`)
}

export function createProject(input: ProjectInput & { key: string; memberIds?: string[] }) {
  return apiFetch<Project>('/projects', { method: 'POST', body: JSON.stringify(input) })
}

export function updateProject(
  projectId: string,
  input: Partial<Omit<ProjectInput, 'key'>> & { version: number },
) {
  return apiFetch<Project>(`/projects/${projectId}`, {
    method: 'PATCH',
    body: JSON.stringify(input),
  })
}

export function archiveProject(projectId: string, version: number) {
  return apiFetch<Project>(`/projects/${projectId}/archive`, {
    method: 'POST',
    body: JSON.stringify({ version }),
  })
}

export function restoreProject(projectId: string, version: number) {
  return apiFetch<Project>(`/projects/${projectId}/restore`, {
    method: 'POST',
    body: JSON.stringify({ version }),
  })
}

export function listMembers(projectId: string) {
  return apiFetch<ProjectMembers>(`/projects/${projectId}/members`)
}

export function addMember(projectId: string, userId: string, version: number) {
  return apiFetch<ProjectMembers>(`/projects/${projectId}/members`, {
    method: 'POST',
    body: JSON.stringify({ userId, version }),
  })
}

export function removeMember(projectId: string, memberId: string, version: number) {
  return apiFetch<ProjectMembers>(
    `/projects/${projectId}/members/${memberId}${toQueryString({ version })}`,
    { method: 'DELETE' },
  )
}

export function searchUsers(q: string) {
  return apiFetch<UserSummary[]>(`/users${toQueryString({ q, limit: 20 })}`)
}
