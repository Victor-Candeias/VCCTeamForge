import { apiFetch, toQueryString } from '@/services/apiClient'
import type { Page, Priority } from '@/services/common'
import type { IssueRef } from '@/services/issues'

export type TestCaseStatus = 'draft' | 'ready' | 'deprecated'
export type TestPlanStatus = 'draft' | 'active' | 'closed'

export const testCaseStatusLabels: Record<TestCaseStatus, string> = {
  draft: 'Rascunho',
  ready: 'Pronto',
  deprecated: 'Obsoleto',
}

export const testPlanStatusLabels: Record<TestPlanStatus, string> = {
  draft: 'Rascunho',
  active: 'Ativo',
  closed: 'Fechado',
}

export type TestStep = { action: string; expectedResult: string }

export type TestCaseSummary = {
  id: string
  projectId: string
  key: string
  number: number
  title: string
  priority: Priority
  status: TestCaseStatus
  labels: string[]
  stepCount: number
  updatedAt: string
  version: number
}

export type TestCase = TestCaseSummary & {
  description: string
  preconditions: string
  steps: TestStep[]
  expectedResult: string
  issues: IssueRef[]
  createdAt: string
  canEdit: boolean
}

export type TestCaseRef = Pick<TestCaseSummary, 'id' | 'key' | 'title' | 'priority' | 'status'>

export type TestCaseFilters = {
  projectId: string
  status?: TestCaseStatus[]
  priority?: Priority[]
  label?: string[]
  issueId?: string
  q?: string
  sort?: string
  page?: number
  pageSize?: number
}

export type TestCaseInput = {
  title: string
  description: string
  preconditions: string
  steps: TestStep[]
  expectedResult: string
  priority: Priority
  status: TestCaseStatus
  labels: string[]
  issueIds: string[]
}

export type TestPlanSummary = {
  id: string
  projectId: string
  name: string
  description: string
  status: TestPlanStatus
  testCaseCount: number
  createdAt: string
  updatedAt: string
  version: number
}

export type TestPlan = TestPlanSummary & {
  testCases: TestCaseRef[]
  issues: IssueRef[]
  canEdit: boolean
}

export type TestPlanFilters = {
  projectId: string
  status?: TestPlanStatus[]
  q?: string
  sort?: string
  page?: number
  pageSize?: number
}

export type TestPlanInput = {
  name: string
  description: string
  status: TestPlanStatus
  testCaseIds: string[]
  issueIds: string[]
}

export function listTestCases(filters: TestCaseFilters) {
  return apiFetch<Page<TestCaseSummary>>(`/test-cases${toQueryString(filters)}`)
}

export function getTestCase(testCaseId: string) {
  return apiFetch<TestCase>(`/test-cases/${testCaseId}`)
}

export function createTestCase(input: TestCaseInput & { projectId: string }) {
  return apiFetch<TestCase>('/test-cases', { method: 'POST', body: JSON.stringify(input) })
}

export function updateTestCase(
  testCaseId: string,
  input: Partial<TestCaseInput> & { version: number },
) {
  return apiFetch<TestCase>(`/test-cases/${testCaseId}`, {
    method: 'PATCH',
    body: JSON.stringify(input),
  })
}

export function listTestPlans(filters: TestPlanFilters) {
  return apiFetch<Page<TestPlanSummary>>(`/test-plans${toQueryString(filters)}`)
}

export function getTestPlan(testPlanId: string) {
  return apiFetch<TestPlan>(`/test-plans/${testPlanId}`)
}

export function createTestPlan(input: TestPlanInput & { projectId: string }) {
  return apiFetch<TestPlan>('/test-plans', { method: 'POST', body: JSON.stringify(input) })
}

export function updateTestPlan(
  testPlanId: string,
  input: Partial<TestPlanInput> & { version: number },
) {
  return apiFetch<TestPlan>(`/test-plans/${testPlanId}`, {
    method: 'PATCH',
    body: JSON.stringify(input),
  })
}
