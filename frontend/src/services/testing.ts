import { apiFetch, toQueryString } from '@/services/apiClient'
import type { Page, Priority, UserSummary } from '@/services/common'
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

// Execuções (DEV-021) -----------------------------------------------------------------------

export type TestRunResult = 'pass' | 'fail' | 'blocked' | 'not_run' | 'skipped'

export const testRunResultLabels: Record<TestRunResult, string> = {
  pass: 'Passou',
  fail: 'Falhou',
  blocked: 'Bloqueado',
  not_run: 'Não executado',
  skipped: 'Ignorado',
}

export type TestRunSummary = {
  id: string
  projectId: string
  testCaseId: string
  testCaseKey: string
  testCaseTitle: string
  testPlanId: string | null
  testPlanName: string | null
  result: TestRunResult
  environment: string
  executedBy: UserSummary | null
  executedAt: string
  bugCount: number
  evidenceCount: number
  version: number
}

export type TestRun = TestRunSummary & {
  actualResult: string
  notes: string
  bugs: IssueRef[]
  createdAt: string
  updatedAt: string
  canEdit: boolean
  canAddEvidence: boolean
  canCreateBug: boolean
}

export type TestRunFilters = {
  projectId: string
  testCaseId?: string
  testPlanId?: string
  result?: TestRunResult[]
  executedBy?: string
  sort?: string
  page?: number
  pageSize?: number
}

export type TestRunInput = {
  testCaseId: string
  testPlanId?: string
  result: TestRunResult
  actualResult: string
  notes: string
  environment: string
}

export type TestRunUpdateInput = Partial<
  Pick<TestRunInput, 'result' | 'actualResult' | 'notes' | 'environment'>
> & { version: number }

export type TestRunBugInput = { title?: string; priority?: Priority; assigneeId?: string }

export type TestRunEvidence = {
  id: string
  testRunId: string
  originalName: string
  contentType: string
  size: number
  sha256: string
  isImage: boolean
  uploadedBy: UserSummary | null
  createdAt: string
  canDelete: boolean
}

export type TestPlanCaseProgress = {
  testCase: TestCaseRef
  lastRunId: string | null
  lastResult: TestRunResult
  lastExecutedAt: string | null
  lastExecutedBy: UserSummary | null
  previousResult: TestRunResult | null
  regression: boolean
}

export type TestPlanProgress = {
  testPlanId: string
  totalCases: number
  counts: Record<TestRunResult, number>
  executedCases: number
  passRate: number | null
  regressions: number
  cases: TestPlanCaseProgress[]
}

export function listTestRuns(filters: TestRunFilters) {
  return apiFetch<Page<TestRunSummary>>(`/test-runs${toQueryString(filters)}`)
}

export function getTestRun(testRunId: string) {
  return apiFetch<TestRun>(`/test-runs/${testRunId}`)
}

export function createTestRun(input: TestRunInput) {
  return apiFetch<TestRun>('/test-runs', { method: 'POST', body: JSON.stringify(input) })
}

export function updateTestRun(testRunId: string, input: TestRunUpdateInput) {
  return apiFetch<TestRun>(`/test-runs/${testRunId}`, {
    method: 'PATCH',
    body: JSON.stringify(input),
  })
}

export function createTestRunBug(testRunId: string, input: TestRunBugInput) {
  return apiFetch<TestRun>(`/test-runs/${testRunId}/bugs`, {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export function getTestPlanProgress(testPlanId: string) {
  return apiFetch<TestPlanProgress>(`/test-plans/${testPlanId}/progress`)
}

export function listTestRunEvidences(testRunId: string) {
  return apiFetch<TestRunEvidence[]>(`/test-runs/${testRunId}/evidences`)
}

export function uploadTestRunEvidence(testRunId: string, file: File) {
  const body = new FormData()
  body.append('file', file)
  return apiFetch<TestRunEvidence>(`/test-runs/${testRunId}/evidences`, { method: 'POST', body })
}

export function deleteTestRunEvidence(testRunId: string, evidenceId: string) {
  return apiFetch<void>(`/test-runs/${testRunId}/evidences/${evidenceId}`, { method: 'DELETE' })
}

export function testRunEvidenceUrl(testRunId: string, evidenceId: string, inline = false) {
  return `/api/test-runs/${testRunId}/evidences/${evidenceId}/content${inline ? '?inline=1' : ''}`
}

export function formatPassRate(value: number | null): string {
  return value === null ? '—' : `${Math.round(value * 1000) / 10}%`.replace('.', ',')
}
