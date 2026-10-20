import { apiFetch, toQueryString } from '@/services/apiClient'
import type { Page, Priority, UserSummary } from '@/services/common'

export type IssueType = 'epic' | 'story' | 'task' | 'bug' | 'spike' | 'improvement' | 'subtask'
export type IssueStatus = 'todo' | 'in_progress' | 'code_review' | 'testing' | 'done'

export const issueTypeLabels: Record<IssueType, string> = {
  epic: 'Epic',
  story: 'Story',
  task: 'Tarefa',
  bug: 'Bug',
  spike: 'Spike',
  improvement: 'Melhoria',
  subtask: 'Subtarefa',
}

export const issueStatusLabels: Record<IssueStatus, string> = {
  todo: 'To Do',
  in_progress: 'Em progresso',
  code_review: 'Code review',
  testing: 'Em testes',
  done: 'Concluída',
}

export const issueStatuses = Object.keys(issueStatusLabels) as IssueStatus[]
export const issueTypes = Object.keys(issueTypeLabels) as IssueType[]

export type IssueRef = {
  id: string
  key: string
  title: string
  type: IssueType
  status: IssueStatus
}

export type IssueSummary = {
  id: string
  projectId: string
  key: string
  number: number
  type: IssueType
  title: string
  status: IssueStatus
  priority: Priority
  assignee: UserSummary | null
  storyPoints: number | null
  labels: string[]
  blocked: boolean
  dueDate: string | null
  parentIssueId: string | null
  sprintId: string | null
  updatedAt: string
  version: number
}

export type Issue = IssueSummary & {
  projectKey: string
  description: string
  reporter: UserSummary | null
  parent: IssueRef | null
  acceptanceCriteria: string[]
  dependsOn: IssueRef[]
  blockReason: string | null
  blockedAt: string | null
  completedAt: string | null
  createdAt: string
  canEdit: boolean
  allowedTransitions: IssueStatus[]
}

export type IssueFields = {
  title: string
  description: string
  priority: Priority
  assigneeId: string | null
  parentIssueId: string | null
  storyPoints: number | null
  labels: string[]
  acceptanceCriteria: string[]
  dueDate: string | null
  dependsOnIssueIds?: string[]
}

export type IssueCreateInput = IssueFields & { projectId: string; type: IssueType }

export type IssueUpdateInput = Partial<IssueFields> & {
  version: number
  status?: IssueStatus
  blocked?: boolean
  blockReason?: string | null
}

/** Indica se `candidate` pode ser pai de uma issue do tipo `type` (hierarquia do backend). */
export function canBeParent(type: IssueType, candidate: IssueSummary) {
  if (type === 'epic') return false
  if (type === 'subtask') return candidate.type !== 'epic' && candidate.type !== 'subtask'
  return candidate.type === 'epic'
}

export type IssueSearchParams = {
  projectId?: string
  status?: IssueStatus[]
  priority?: Priority[]
  type?: IssueType[]
  assigneeId?: string[]
  sprintId?: string
  label?: string[]
  blocked?: boolean
  parentIssueId?: string
  q?: string
  sort?: string
  page?: number
  pageSize?: number
}

export const issueSortFields = [
  'number',
  'title',
  'status',
  'priority',
  'updatedAt',
  'createdAt',
  'dueDate',
] as const
export type IssueSortField = (typeof issueSortFields)[number]

export function searchIssues(params: IssueSearchParams) {
  return apiFetch<Page<IssueSummary>>(`/issues${toQueryString(params)}`)
}

export function listProjectLabels(projectId: string) {
  return apiFetch<string[]>(`/projects/${projectId}/labels`)
}

export function getIssueByKey(key: string) {
  return apiFetch<Issue>(`/issues/by-key/${encodeURIComponent(key)}`)
}

export function createIssue(input: IssueCreateInput) {
  return apiFetch<Issue>('/issues', { method: 'POST', body: JSON.stringify(input) })
}

export function updateIssue(issueId: string, input: IssueUpdateInput) {
  return apiFetch<Issue>(`/issues/${issueId}`, { method: 'PATCH', body: JSON.stringify(input) })
}
