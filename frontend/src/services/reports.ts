import { apiFetch } from '@/services/apiClient'
import type { IssueStatus } from '@/services/issues'
import type { SprintStatus } from '@/services/sprints'

export type SprintReportKpis = {
  committedIssueCount: number
  committedStoryPoints: number
  issueCount: number
  storyPoints: number
  unestimatedCount: number
  completedIssueCount: number
  completedStoryPoints: number
  remainingStoryPoints: number
  progressPercent: number | null
  totalDays: number
  elapsedDays: number
  remainingDays: number
  blockedCount: number
  addedCount: number
  removedCount: number
}

export type BurndownPoint = {
  day: string
  ideal: number
  remaining: number | null
  scope: number | null
}

export type StatusBreakdown = {
  status: IssueStatus
  issueCount: number
  storyPoints: number
}

export type BlockedIssue = {
  issueId: string
  key: string
  title: string
  status: IssueStatus
  blockReason: string | null
  blockedAt: string | null
}

export type VelocityEntry = {
  sprintId: string
  name: string
  committedStoryPoints: number
  completedStoryPoints: number
  committedCompletedStoryPoints: number
  predictabilityPercent: number | null
}

export type SprintReport = {
  sprintId: string
  name: string
  goal: string
  status: SprintStatus
  startDate: string
  endDate: string
  asOf: string
  kpis: SprintReportKpis
  burndown: BurndownPoint[]
  statusBreakdown: StatusBreakdown[]
  blockedIssues: BlockedIssue[]
  velocity: VelocityEntry[]
  averageVelocity: number | null
}

export function getSprintReport(sprintId: string) {
  return apiFetch<SprintReport>(`/reports/sprints/${sprintId}`)
}
