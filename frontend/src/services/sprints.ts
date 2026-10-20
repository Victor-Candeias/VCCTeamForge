import { apiFetch, toQueryString } from '@/services/apiClient'
import type { Page } from '@/services/common'
import type { IssueStatus, IssueType } from '@/services/issues'

export type SprintStatus = 'planned' | 'active' | 'closed'

export const sprintStatusLabels: Record<SprintStatus, string> = {
  planned: 'Planeado',
  active: 'Ativo',
  closed: 'Fechado',
}

export type SprintScope = {
  issueCount: number
  storyPoints: number
  unestimatedCount: number
  completedIssueCount: number
  completedStoryPoints: number
}

export type SprintResult = {
  completedIssueCount: number
  completedStoryPoints: number
  carriedOverIssueCount: number
  carriedOverStoryPoints: number
  carryOverSprintId: string | null
  committedCompletedIssueCount: number
  committedCompletedStoryPoints: number
}

export type SprintRetrospective = {
  wentWell: string
  toImprove: string
  actions: string
}

export type Sprint = {
  id: string
  projectId: string
  name: string
  goal: string
  status: SprintStatus
  startDate: string
  endDate: string
  durationDays: number
  capacityStoryPoints: number | null
  scope: SprintScope
  committedStoryPoints: number | null
  committedIssueCount: number | null
  startedAt: string | null
  closedAt: string | null
  result: SprintResult | null
  retrospective: SprintRetrospective | null
  createdAt: string
  updatedAt: string
  version: number
  canEdit: boolean
}

export type CommittedIssue = {
  issueId: string
  key: string
  title: string
  type: IssueType
  status: IssueStatus
  storyPoints: number | null
  currentStatus: IssueStatus | null
  currentStoryPoints: number | null
  inSprint: boolean
}

export type AddedIssue = {
  issueId: string
  key: string
  title: string
  type: IssueType
  status: IssueStatus
  storyPoints: number | null
}

export type SprintCommitment = {
  sprintId: string
  takenAt: string
  issueCount: number
  storyPoints: number
  unestimatedCount: number
  removedCount: number
  addedCount: number
  addedStoryPoints: number
  issues: CommittedIssue[]
  added: AddedIssue[]
}

export type SprintFilters = {
  projectId: string
  status?: SprintStatus[]
  sort?: string
  page?: number
  pageSize?: number
}

export type SprintInput = {
  name: string
  goal: string
  startDate: string
  endDate: string | null
  capacityStoryPoints?: number | null
}

export function listSprints(filters: SprintFilters) {
  return apiFetch<Page<Sprint>>(`/sprints${toQueryString(filters)}`)
}

export function getSprint(sprintId: string) {
  return apiFetch<Sprint>(`/sprints/${sprintId}`)
}

export function createSprint(input: SprintInput & { projectId: string }) {
  return apiFetch<Sprint>('/sprints', { method: 'POST', body: JSON.stringify(input) })
}

export function updateSprint(sprintId: string, input: Partial<SprintInput> & { version: number }) {
  return apiFetch<Sprint>(`/sprints/${sprintId}`, {
    method: 'PATCH',
    body: JSON.stringify(input),
  })
}

export function addSprintIssues(sprintId: string, issueIds: string[]) {
  return apiFetch<Sprint>(`/sprints/${sprintId}/issues`, {
    method: 'POST',
    body: JSON.stringify({ issueIds }),
  })
}

export function removeSprintIssue(sprintId: string, issueId: string) {
  return apiFetch<Sprint>(`/sprints/${sprintId}/issues/${issueId}`, { method: 'DELETE' })
}

export function startSprint(sprintId: string, version: number) {
  return apiFetch<Sprint>(`/sprints/${sprintId}/start`, {
    method: 'POST',
    body: JSON.stringify({ version }),
  })
}

export type SprintCloseInput = {
  version: number
  carryOverSprintId: string | null
  retrospective: SprintRetrospective
}

export function closeSprint(sprintId: string, input: SprintCloseInput) {
  return apiFetch<Sprint>(`/sprints/${sprintId}/close`, {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export function getSprintCommitment(sprintId: string) {
  return apiFetch<SprintCommitment>(`/sprints/${sprintId}/commitment`)
}

/** Soma dias a uma data `AAAA-MM-DD` (em UTC, sem efeitos de fuso horário). */
export function addDays(value: string, days: number): string {
  const date = new Date(`${value}T00:00:00Z`)
  date.setUTCDate(date.getUTCDate() + days)
  return date.toISOString().slice(0, 10)
}
