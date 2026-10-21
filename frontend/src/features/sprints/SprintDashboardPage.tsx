import type { ReactNode } from 'react'
import { Link, useParams } from 'react-router'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
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
import { useProjectContext } from '@/features/projects/projectContext'
import { SprintStatusBadge } from '@/features/sprints/SprintsPage'
import { useSprint, useSprintReport } from '@/features/sprints/useSprints'
import { ApiError } from '@/services/apiClient'
import { formatDate, formatDateTime } from '@/services/common'
import { issueStatusLabels } from '@/services/issues'
import type { SprintReport } from '@/services/reports'

const CHART_HEIGHT = 280
const CHART_INITIAL_SIZE = { width: 600, height: CHART_HEIGHT }
const BAR_RADIUS: [number, number, number, number] = [4, 4, 0, 0]

function formatPoints(value: number | null) {
  return value === null ? '—' : value.toLocaleString('pt-PT', { maximumFractionDigits: 1 })
}

function formatPercent(value: number | null) {
  return value === null ? '—' : `${formatPoints(value)}%`
}

function Kpi({ label, value, hint }: { label: string; value: string; hint?: string }) {
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

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-2">
      <h3 className="text-lg font-semibold">{title}</h3>
      {children}
    </section>
  )
}

function Kpis({ report }: { report: SprintReport }) {
  const { kpis } = report
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <Kpi
        label="Progresso"
        value={formatPercent(kpis.progressPercent)}
        hint={`${formatPoints(kpis.completedStoryPoints)} de ${formatPoints(kpis.storyPoints)} story points`}
      />
      <Kpi
        label="Story points restantes"
        value={formatPoints(kpis.remainingStoryPoints)}
        hint={`${kpis.completedIssueCount} de ${kpis.issueCount} issues concluídas`}
      />
      <Kpi
        label="Compromisso"
        value={`${formatPoints(kpis.committedStoryPoints)} SP`}
        hint={`${kpis.committedIssueCount} issues · ${kpis.addedCount} adicionadas, ${kpis.removedCount} retiradas`}
      />
      <Kpi
        label="Dias restantes"
        value={String(kpis.remainingDays)}
        hint={`${kpis.elapsedDays} de ${kpis.totalDays} dias decorridos`}
      />
      <Kpi label="Bloqueadas" value={String(kpis.blockedCount)} />
      <Kpi label="Sem estimativa" value={String(kpis.unestimatedCount)} />
    </div>
  )
}

function Burndown({ report }: { report: SprintReport }) {
  const data = report.burndown.map((point) => ({ ...point, label: formatDate(point.day).slice(0, 5) }))
  return (
    <Section title="Burndown">
      <div className="h-[280px] w-full" aria-label="Gráfico de burndown" role="img">
        <ResponsiveContainer
          width="100%"
          height={CHART_HEIGHT}
          initialDimension={CHART_INITIAL_SIZE}
        >
          <LineChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
            <XAxis dataKey="label" />
            <YAxis allowDecimals={false} />
            <Tooltip formatter={(value) => formatPoints(typeof value === 'number' ? value : null)} />
            <Legend />
            <Line
              name="Ideal"
              dataKey="ideal"
              stroke="var(--muted-foreground)"
              strokeDasharray="5 5"
              dot={false}
            />
            <Line name="Restante" dataKey="remaining" stroke="var(--primary)" strokeWidth={2} />
            <Line
              name="Âmbito"
              dataKey="scope"
              stroke="var(--warning)"
              type="stepAfter"
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Section>
  )
}

function StatusBars({ report }: { report: SprintReport }) {
  const total = Math.max(report.kpis.issueCount, 1)
  return (
    <Section title="Distribuição por estado">
      <ul className="space-y-2">
        {report.statusBreakdown.map((item) => (
          <li key={item.status} className="grid grid-cols-[8rem_1fr_7rem] items-center gap-3 text-sm">
            <span>{issueStatusLabels[item.status]}</span>
            <span className="h-2 rounded bg-muted">
              <span
                className="block h-2 rounded bg-primary"
                style={{ width: `${(item.issueCount / total) * 100}%` }}
              />
            </span>
            <span className="text-right text-muted-foreground">
              {item.issueCount} · {formatPoints(item.storyPoints)} SP
            </span>
          </li>
        ))}
      </ul>
    </Section>
  )
}

function BlockedIssues({ report }: { report: SprintReport }) {
  return (
    <Section title="Issues bloqueadas">
      {report.blockedIssues.length === 0 ? (
        <p className="text-muted-foreground">Sem issues bloqueadas.</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-24">Chave</TableHead>
              <TableHead>Título</TableHead>
              <TableHead>Estado</TableHead>
              <TableHead>Motivo</TableHead>
              <TableHead>Desde</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {report.blockedIssues.map((issue) => (
              <TableRow key={issue.issueId}>
                <TableCell>
                  <Link className="font-mono hover:underline" to={`/issues/${issue.key}`}>
                    {issue.key}
                  </Link>
                </TableCell>
                <TableCell>{issue.title}</TableCell>
                <TableCell>
                  <IssueStatusBadge status={issue.status} />
                </TableCell>
                <TableCell>{issue.blockReason ?? '—'}</TableCell>
                <TableCell>{formatDateTime(issue.blockedAt)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </Section>
  )
}

function Velocity({ report }: { report: SprintReport }) {
  return (
    <Section title="Velocidade">
      {report.velocity.length === 0 ? (
        <p className="text-muted-foreground">Ainda não há sprints fechados.</p>
      ) : (
        <>
          <p className="text-sm text-muted-foreground">
            Média: {formatPoints(report.averageVelocity)} story points concluídos por sprint.
          </p>
          <div className="h-[280px] w-full" aria-label="Gráfico de velocidade" role="img">
            <ResponsiveContainer
          width="100%"
          height={CHART_HEIGHT}
          initialDimension={CHART_INITIAL_SIZE}
        >
              <BarChart data={report.velocity} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                <XAxis dataKey="name" />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Legend />
                <Bar
                  name="Compromisso"
                  dataKey="committedStoryPoints"
                  fill="var(--chart-2)"
                  radius={BAR_RADIUS}
                />
                <Bar
                  name="Concluído"
                  dataKey="completedStoryPoints"
                  fill="var(--chart-1)"
                  radius={BAR_RADIUS}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Sprint</TableHead>
                <TableHead>Compromisso</TableHead>
                <TableHead>Concluído</TableHead>
                <TableHead>Do compromisso</TableHead>
                <TableHead>Previsibilidade</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {report.velocity.map((entry) => (
                <TableRow key={entry.sprintId}>
                  <TableCell>{entry.name}</TableCell>
                  <TableCell>{formatPoints(entry.committedStoryPoints)}</TableCell>
                  <TableCell>{formatPoints(entry.completedStoryPoints)}</TableCell>
                  <TableCell>{formatPoints(entry.committedCompletedStoryPoints)}</TableCell>
                  <TableCell>{formatPercent(entry.predictabilityPercent)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </>
      )}
    </Section>
  )
}

export function SprintDashboardPage() {
  const { project } = useProjectContext()
  const { sprintId = '' } = useParams()
  const sprint = useSprint(sprintId)
  const report = useSprintReport(sprintId, sprint.data?.projectId === project.id)
  const back = (
    <Button variant="ghost" asChild>
      <Link to={`/projects/${project.id}/sprints/${sprintId}`}>Voltar ao sprint</Link>
    </Button>
  )

  if (sprint.isPending) return <p className="text-muted-foreground">A carregar…</p>
  if (sprint.isError || sprint.data.projectId !== project.id) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Sprint não encontrado ou sem acesso.</AlertDescription>
      </Alert>
    )
  }
  if (report.isError) {
    const notStarted = report.error instanceof ApiError && report.error.status === 422
    return (
      <div className="space-y-4">
        <Alert variant={notStarted ? 'default' : 'destructive'}>
          <AlertDescription>
            {notStarted
              ? 'O dashboard fica disponível depois de iniciar o sprint.'
              : 'Não foi possível carregar o dashboard do sprint.'}
          </AlertDescription>
        </Alert>
        {back}
      </div>
    )
  }
  if (report.isPending) return <p className="text-muted-foreground">A carregar…</p>

  const data = report.data
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-semibold">Dashboard · {data.name}</h2>
            <SprintStatusBadge status={data.status} />
          </div>
          <p className="text-sm text-muted-foreground">
            {formatDate(data.startDate)} – {formatDate(data.endDate)} · dados de{' '}
            {formatDateTime(data.asOf)}
          </p>
          {data.goal && <p className="max-w-2xl">{data.goal}</p>}
        </div>
        {back}
      </div>
      <Kpis report={data} />
      <Burndown report={data} />
      <div className="grid gap-6 lg:grid-cols-2">
        <StatusBars report={data} />
        <BlockedIssues report={data} />
      </div>
      <Velocity report={data} />
    </div>
  )
}
