import type { ReactNode } from 'react'
import { Link } from 'react-router'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { IssueStatusBadge } from '@/features/issues/IssueBadges'
import { formatNumber, formatRate } from '@/features/analytics/format'
import type { AnalyticsIssue, AnalyticsKpis } from '@/services/analytics'
import { priorityLabels } from '@/services/common'
import { issueStatusLabels } from '@/services/issues'
import type { StatusBreakdown } from '@/services/reports'

export function Kpi({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle className="text-sm text-muted-foreground">{label}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-2xl font-semibold">{value}</p>
        {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      </CardContent>
    </Card>
  )
}

export function KpiGrid({ kpis }: { kpis: AnalyticsKpis }) {
  return (
    <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
      <Kpi
        label="Abertas"
        value={String(kpis.openCount)}
        hint={`${formatNumber(kpis.openStoryPoints)} SP por concluir`}
      />
      <Kpi label="Em progresso" value={String(kpis.inProgressCount)} />
      <Kpi label="Bloqueadas" value={String(kpis.blockedCount)} />
      <Kpi label="Concluídas" value={String(kpis.doneCount)} />
      <Kpi label="Bugs críticos" value={String(kpis.criticalBugCount)} hint="Por concluir" />
      <Kpi
        label="Testes aprovados"
        value={formatRate(kpis.testPassRate)}
        hint={`${kpis.testRunCount} execuções`}
      />
    </div>
  )
}

export function Section({
  title,
  description,
  children,
}: {
  title: string
  description?: string
  children: ReactNode
}) {
  return (
    <section className="space-y-2">
      <h3 className="text-lg font-semibold">{title}</h3>
      {description && <p className="text-sm text-muted-foreground">{description}</p>}
      {children}
    </section>
  )
}

export function StatusBars({ breakdown }: { breakdown: StatusBreakdown[] }) {
  const total = Math.max(
    breakdown.reduce((sum, item) => sum + item.issueCount, 0),
    1,
  )
  return (
    <ul className="space-y-2" aria-label="Distribuição por estado">
      {breakdown.map((item) => (
        <li key={item.status} className="grid grid-cols-[8rem_1fr_7rem] items-center gap-3 text-sm">
          <span>{issueStatusLabels[item.status]}</span>
          <span className="h-2 rounded bg-muted">
            <span
              className="block h-2 rounded bg-primary"
              style={{ width: `${(item.issueCount / total) * 100}%` }}
            />
          </span>
          <span className="text-right text-muted-foreground">
            {item.issueCount} · {formatNumber(item.storyPoints)} SP
          </span>
        </li>
      ))}
    </ul>
  )
}

export function IssueTable({
  issues,
  sinceLabel,
  empty,
}: {
  issues: AnalyticsIssue[]
  sinceLabel: string
  empty: string
}) {
  if (issues.length === 0) return <p className="text-sm text-muted-foreground">{empty}</p>
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-24">Chave</TableHead>
          <TableHead>Título</TableHead>
          <TableHead>Estado</TableHead>
          <TableHead>Prioridade</TableHead>
          <TableHead>Responsável</TableHead>
          <TableHead>{sinceLabel}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {issues.map((issue) => (
          <TableRow key={issue.id}>
            <TableCell>
              <Link className="font-mono hover:underline" to={`/issues/${issue.key}`}>
                {issue.key}
              </Link>
            </TableCell>
            <TableCell>{issue.title}</TableCell>
            <TableCell>
              <IssueStatusBadge status={issue.status} />
            </TableCell>
            <TableCell>{priorityLabels[issue.priority]}</TableCell>
            <TableCell>{issue.assignee?.name ?? '—'}</TableCell>
            <TableCell>{issue.ageDays} d</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
