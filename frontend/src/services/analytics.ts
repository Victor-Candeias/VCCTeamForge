import { apiDownload, apiFetch, toQueryString } from '@/services/apiClient'
import type { Priority, UserSummary } from '@/services/common'
import type { IssueStatus, IssueType } from '@/services/issues'
import type { ReleaseStatus } from '@/services/releases'
import type { StatusBreakdown, VelocityEntry } from '@/services/reports'
import type { SprintStatus } from '@/services/sprints'

export type AnalyticsKpis = {
  openCount: number
  inProgressCount: number
  blockedCount: number
  doneCount: number
  criticalBugCount: number
  openStoryPoints: number
  /** Fração 0–1; `null` sem execuções relevantes. */
  testPassRate: number | null
  testRunCount: number
}

export type AnalyticsIssue = {
  id: string
  key: string
  title: string
  projectId: string
  type: IssueType
  status: IssueStatus
  priority: Priority
  assignee: UserSummary | null
  since: string
  ageDays: number
}

export type AlertKind = 'blocked' | 'stale' | 'unassigned_critical_bugs'

export type AlertGroup = {
  kind: AlertKind
  label: string
  total: number
  issues: AnalyticsIssue[]
}

export type ActiveSprintSummary = {
  sprintId: string
  projectId: string
  projectKey: string
  projectName: string
  name: string
  goal: string
  startDate: string
  endDate: string
  remainingDays: number
  issueCount: number
  completedIssueCount: number
  storyPoints: number
  completedStoryPoints: number
  progressPercent: number | null
}

export type TrendPoint = {
  day: string
  openCount: number
  inProgressCount: number
  blockedCount: number
  doneCount: number
  criticalBugCount: number
  openStoryPoints: number
}

export type DashboardOverview = {
  projectId: string | null
  projectCount: number
  kpis: AnalyticsKpis
  statusBreakdown: StatusBreakdown[]
  activeSprints: ActiveSprintSummary[]
  alerts: AlertGroup[]
  myWork: {
    openCount: number
    inProgressCount: number
    blockedCount: number
    issues: AnalyticsIssue[]
  }
  trend: TrendPoint[]
  generatedAt: string
}

export type DurationMetric = {
  count: number
  averageDays: number | null
  medianDays: number | null
  p85Days: number | null
}

export type ProjectMetrics = {
  projectId: string
  filters: { sprintId: string | null; type: IssueType | null; from: string; to: string }
  kpis: AnalyticsKpis
  statusBreakdown: StatusBreakdown[]
  velocity: {
    sprints: VelocityEntry[]
    averageVelocity: number | null
    averagePredictabilityPercent: number | null
  }
  leadTime: DurationMetric
  cycleTime: DurationMetric
  aging: {
    buckets: { label: string; minDays: number; maxDays: number | null; count: number }[]
    oldest: AnalyticsIssue[]
  }
  bugSeverity: { priority: Priority; open: number; done: number; total: number }[]
  qa: { runCount: number; counts: Record<string, number>; passRate: number | null }
  releases: {
    releaseId: string
    name: string
    status: ReleaseStatus
    plannedDate: string | null
    releasedAt: string | null
    issueCount: number
    doneIssueCount: number
    knownBugCount: number
    openBugCount: number
    openCriticalBugCount: number
    testPassRate: number | null
    ready: boolean
  }[]
  workload: {
    assignee: UserSummary | null
    openCount: number
    inProgressCount: number
    blockedCount: number
    openStoryPoints: number
  }[]
  trend: TrendPoint[]
  sprints: { id: string; name: string; status: SprintStatus }[]
  generatedAt: string
}

export type MetricsParams = {
  sprintId?: string
  type?: IssueType
  from?: string
  to?: string
}

export type ExportFormat = 'csv' | 'xlsx' | 'pdf'

export const exportFormatLabels: Record<ExportFormat, string> = {
  csv: 'CSV',
  xlsx: 'XLSX',
  pdf: 'PDF',
}

export type ReportSnapshot = {
  projectId: string
  day: string
  kpis: AnalyticsKpis
  statusBreakdown: StatusBreakdown[]
  takenAt: string
}

export function getDashboardOverview(projectId?: string) {
  return apiFetch<DashboardOverview>(`/dashboard/overview${toQueryString({ projectId })}`)
}

export function getProjectMetrics(projectId: string, params: MetricsParams = {}) {
  return apiFetch<ProjectMetrics>(`/reports/projects/${projectId}/metrics${toQueryString(params)}`)
}

export function createReportSnapshot(projectId: string) {
  return apiFetch<ReportSnapshot>(`/reports/projects/${projectId}/snapshots`, { method: 'POST' })
}

export function exportReport(projectId: string, format: ExportFormat, params: MetricsParams = {}) {
  return apiDownload(`/reports/export${toQueryString({ projectId, format, ...params })}`)
}
