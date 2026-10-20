import { apiFetch, toQueryString } from '@/services/apiClient'
import type { Page, UserSummary } from '@/services/common'
import type { IssueRef } from '@/services/issues'
import type { TestPlanStatus, TestRunResult } from '@/services/testing'

export type ReleaseStatus = 'draft' | 'ready_for_qa' | 'approved' | 'released'
export type ReleaseCriterionKey = 'issuesDone' | 'testsPassed' | 'noOpenCriticalBugs'

export const releaseStatusLabels: Record<ReleaseStatus, string> = {
  draft: 'Rascunho',
  ready_for_qa: 'Pronta para QA',
  approved: 'Aprovada',
  released: 'Publicada',
}

export const releaseCriteriaLabels: Record<ReleaseCriterionKey, string> = {
  issuesDone: 'Todas as issues incluídas concluídas',
  testsPassed: 'Testes dos planos associados aprovados',
  noOpenCriticalBugs: 'Sem bugs críticos em aberto',
}

export const releaseHistoryLabels: Record<string, string> = {
  created: 'Criada',
  updated: 'Alterada',
  submitted: 'Enviada para QA',
  approved: 'Aprovada',
  rejected: 'Rejeitada',
  reopened: 'Reaberta',
  released: 'Publicada',
}

export type ReleaseCriteria = Record<ReleaseCriterionKey, boolean>

export type ReleaseChecklistItem = {
  id: string
  label: string
  required: boolean
  done: boolean
  doneBy: UserSummary | null
  doneAt: string | null
}

export type ReleaseChecklistInput = {
  id?: string
  label: string
  required: boolean
  done: boolean
}

export type ReleaseSummary = {
  id: string
  projectId: string
  name: string
  status: ReleaseStatus
  plannedDate: string | null
  releasedAt: string | null
  issueCount: number
  knownBugCount: number
  checklistDone: number
  checklistTotal: number
  createdAt: string
  updatedAt: string
  version: number
}

export type ReleaseQuality = {
  issues: { total: number; done: number }
  knownBugs: { total: number; open: number; openCritical: number }
  tests: {
    plans: number
    totalCases: number
    executedCases: number
    counts: Record<TestRunResult, number>
    passRate: number | null
    regressions: number
  }
  criteria: {
    key: ReleaseCriterionKey
    label: string
    enabled: boolean
    passed: boolean
    detail: string
  }[]
  ready: boolean
}

export type ReleaseHistoryEntry = {
  action: string
  fromStatus: ReleaseStatus | null
  toStatus: ReleaseStatus | null
  fields: string[]
  comment: string
  user: UserSummary | null
  at: string
}

export type TestPlanRef = { id: string; name: string; status: TestPlanStatus }

export type Release = ReleaseSummary & {
  description: string
  notes: string
  issues: IssueRef[]
  knownBugs: IssueRef[]
  testPlans: TestPlanRef[]
  checklist: ReleaseChecklistItem[]
  criteria: ReleaseCriteria
  quality: ReleaseQuality
  history: ReleaseHistoryEntry[]
  canEdit: boolean
  availableTransitions: ReleaseStatus[]
}

export type ReleaseFilters = {
  projectId: string
  status?: ReleaseStatus[]
  q?: string
  sort?: string
  page?: number
  pageSize?: number
}

export type ReleaseInput = {
  name: string
  description: string
  notes: string
  plannedDate: string | null
  issueIds: string[]
  knownBugIds: string[]
  testPlanIds: string[]
  checklist?: ReleaseChecklistInput[]
  criteria: ReleaseCriteria
}

export type ReleaseTransitionInput = {
  to: ReleaseStatus
  comment?: string
  version: number
}

export function listReleases(filters: ReleaseFilters) {
  return apiFetch<Page<ReleaseSummary>>(`/releases${toQueryString(filters)}`)
}

export function getRelease(releaseId: string) {
  return apiFetch<Release>(`/releases/${releaseId}`)
}

export function createRelease(input: ReleaseInput & { projectId: string }) {
  return apiFetch<Release>('/releases', {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export function updateRelease(
  releaseId: string,
  input: Partial<ReleaseInput> & { version: number },
) {
  return apiFetch<Release>(`/releases/${releaseId}`, {
    method: 'PATCH',
    body: JSON.stringify(input),
  })
}

export function transitionRelease(releaseId: string, input: ReleaseTransitionInput) {
  return apiFetch<Release>(`/releases/${releaseId}/transitions`, {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

/** Itens da checklist no formato aceite pela API. */
export function checklistInput(items: ReleaseChecklistItem[]): ReleaseChecklistInput[] {
  return items.map(({ id, label, required, done }) => ({
    id,
    label,
    required,
    done,
  }))
}
