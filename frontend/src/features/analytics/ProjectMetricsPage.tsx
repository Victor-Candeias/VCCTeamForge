import { useState, type ReactNode } from 'react'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { StatusChart, TrendChart, VelocityChart } from '@/features/analytics/AnalyticsCharts'
import { IssueTable, Kpi, KpiGrid, Section, StatusBars } from '@/features/analytics/AnalyticsShared'
import { formatDays, formatNumber, formatPercent, formatRate } from '@/features/analytics/format'
import {
  useCreateReportSnapshot,
  useExportReport,
  useProjectMetrics,
} from '@/features/analytics/useAnalytics'
import { useProjectContext } from '@/features/projects/projectContext'
import { ReleaseStatusBadge } from '@/features/releases/ReleaseShared'
import {
  exportFormatLabels,
  type DurationMetric,
  type ExportFormat,
  type MetricsParams,
  type ProjectMetrics,
} from '@/services/analytics'
import { ApiError } from '@/services/apiClient'
import { formatDate, formatDateTime, priorityLabels } from '@/services/common'
import { issueTypeLabels, issueTypes, type IssueType } from '@/services/issues'
import { testRunResultLabels, type TestRunResult } from '@/services/testing'

function Filters({
  metrics,
  params,
  onChange,
}: {
  metrics: ProjectMetrics | undefined
  params: MetricsParams
  onChange: (params: MetricsParams) => void
}) {
  const set = (key: keyof MetricsParams, value: string) =>
    onChange({ ...params, [key]: value || undefined })
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <div className="space-y-1">
        <Label htmlFor="metrics-sprint">Sprint</Label>
        <NativeSelect
          id="metrics-sprint"
          value={params.sprintId ?? ''}
          onChange={(event) => set('sprintId', event.target.value)}
        >
          <option value="">Todos</option>
          {metrics?.sprints.map((sprint) => (
            <option key={sprint.id} value={sprint.id}>
              {sprint.name}
            </option>
          ))}
        </NativeSelect>
      </div>
      <div className="space-y-1">
        <Label htmlFor="metrics-type">Tipo de issue</Label>
        <NativeSelect
          id="metrics-type"
          value={params.type ?? ''}
          onChange={(event) => set('type', event.target.value as IssueType | '')}
        >
          <option value="">Todos</option>
          {issueTypes.map((type) => (
            <option key={type} value={type}>
              {issueTypeLabels[type]}
            </option>
          ))}
        </NativeSelect>
      </div>
      <div className="space-y-1">
        <Label htmlFor="metrics-from">De</Label>
        <Input
          id="metrics-from"
          type="date"
          value={params.from ?? metrics?.filters.from ?? ''}
          onChange={(event) => set('from', event.target.value)}
        />
      </div>
      <div className="space-y-1">
        <Label htmlFor="metrics-to">Até</Label>
        <Input
          id="metrics-to"
          type="date"
          value={params.to ?? metrics?.filters.to ?? ''}
          onChange={(event) => set('to', event.target.value)}
        />
      </div>
    </div>
  )
}

function Duration({
  label,
  metric,
  hint,
}: {
  label: string
  metric: DurationMetric
  hint: string
}) {
  return (
    <Kpi
      label={label}
      value={formatDays(metric.averageDays)}
      hint={`${hint} · mediana ${formatDays(metric.medianDays)} · p85 ${formatDays(metric.p85Days)} · ${metric.count} issues`}
    />
  )
}

function SimpleTable({ head, rows }: { head: string[]; rows: ReactNode[][] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          {head.map((label) => (
            <TableHead key={label}>{label}</TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((cells, index) => (
          <TableRow key={index}>
            {cells.map((cell, cellIndex) => (
              <TableCell key={cellIndex}>{cell}</TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

function Metrics({ metrics }: { metrics: ProjectMetrics }) {
  const { velocity, aging, qa } = metrics
  return (
    <>
      <KpiGrid kpis={metrics.kpis} />
      <div className="grid gap-6 lg:grid-cols-2">
        <Section title="Distribuição por estado">
          <StatusChart breakdown={metrics.statusBreakdown} />
          <StatusBars breakdown={metrics.statusBreakdown} />
        </Section>
        <Section title="Tendências" description="Snapshots diários do projeto no período.">
          <TrendChart points={metrics.trend} />
        </Section>
      </div>

      <Section
        title="Velocidade e previsibilidade"
        description={`Média: ${formatNumber(velocity.averageVelocity)} SP por sprint · previsibilidade ${formatPercent(velocity.averagePredictabilityPercent)}`}
      >
        {velocity.sprints.length === 0 ? (
          <p className="text-sm text-muted-foreground">Sem sprints fechados no período.</p>
        ) : (
          <>
            <VelocityChart entries={velocity.sprints} />
            <SimpleTable
              head={['Sprint', 'Compromisso', 'Concluído', 'Do compromisso', 'Previsibilidade']}
              rows={velocity.sprints.map((entry) => [
                entry.name,
                formatNumber(entry.committedStoryPoints),
                formatNumber(entry.completedStoryPoints),
                formatNumber(entry.committedCompletedStoryPoints),
                formatPercent(entry.predictabilityPercent),
              ])}
            />
          </>
        )}
      </Section>

      <Section title="Fluxo" description="Issues concluídas no período.">
        <div className="grid gap-3 sm:grid-cols-2">
          <Duration label="Lead time" metric={metrics.leadTime} hint="Criação → conclusão" />
          <Duration label="Cycle time" metric={metrics.cycleTime} hint="Início → conclusão" />
        </div>
      </Section>

      <div className="grid gap-6 lg:grid-cols-2">
        <Section title="Aging" description="Idade das issues por concluir.">
          <SimpleTable
            head={['Idade', 'Issues']}
            rows={aging.buckets.map((bucket) => [bucket.label, bucket.count])}
          />
        </Section>
        <Section title="Bugs por severidade">
          <SimpleTable
            head={['Prioridade', 'Abertos', 'Concluídos', 'Total']}
            rows={metrics.bugSeverity.map((row) => [
              priorityLabels[row.priority],
              row.open,
              row.done,
              row.total,
            ])}
          />
        </Section>
      </div>
      <Section title="Issues abertas mais antigas">
        <IssueTable issues={aging.oldest} sinceLabel="Idade" empty="Sem issues por concluir." />
      </Section>

      <div className="grid gap-6 lg:grid-cols-2">
        <Section
          title="QA"
          description={`Pass rate ${formatRate(qa.passRate)} em ${qa.runCount} execuções (skipped e não executados não contam).`}
        >
          <SimpleTable
            head={['Resultado', 'Execuções']}
            rows={Object.entries(qa.counts).map(([result, count]) => [
              testRunResultLabels[result as TestRunResult] ?? result,
              count,
            ])}
          />
        </Section>
        <Section
          title="Carga de trabalho"
          description="Trabalho em aberto por responsável; não mede desempenho individual."
        >
          {metrics.workload.length === 0 ? (
            <p className="text-sm text-muted-foreground">Sem issues por concluir.</p>
          ) : (
            <SimpleTable
              head={['Responsável', 'Abertas', 'Em progresso', 'Bloqueadas', 'SP em aberto']}
              rows={metrics.workload.map((row) => [
                row.assignee?.name ?? 'Sem responsável',
                row.openCount,
                row.inProgressCount,
                row.blockedCount,
                formatNumber(row.openStoryPoints),
              ])}
            />
          )}
        </Section>
      </div>

      <Section title="Qualidade das releases" description="As 10 releases mais recentes.">
        {metrics.releases.length === 0 ? (
          <p className="text-sm text-muted-foreground">Sem releases.</p>
        ) : (
          <SimpleTable
            head={['Versão', 'Estado', 'Data', 'Issues', 'Bugs abertos', 'Testes', 'Pronta']}
            rows={metrics.releases.map((release) => [
              release.name,
              <ReleaseStatusBadge key="status" status={release.status} />,
              formatDate(release.releasedAt ?? release.plannedDate),
              `${release.doneIssueCount}/${release.issueCount}`,
              `${release.openBugCount} (${release.openCriticalBugCount} críticos)`,
              formatRate(release.testPassRate),
              release.ready ? (
                <Badge key="ready">Sim</Badge>
              ) : (
                <Badge key="ready" variant="secondary">
                  Não
                </Badge>
              ),
            ])}
          />
        )}
      </Section>
    </>
  )
}

export function ProjectMetricsPage() {
  const { project } = useProjectContext()
  const [params, setParams] = useState<MetricsParams>({})
  const metrics = useProjectMetrics(project.id, params)
  const snapshot = useCreateReportSnapshot(project.id)
  const exporter = useExportReport(project.id)
  const canSnapshot = project.canManage && project.status !== 'archived'

  const invalid =
    metrics.error instanceof ApiError && metrics.error.status === 422 ? metrics.error.message : null

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1">
          <h2 className="text-xl font-semibold">Métricas</h2>
          {metrics.data && (
            <p className="text-sm text-muted-foreground">
              {formatDate(metrics.data.filters.from)} – {formatDate(metrics.data.filters.to)} ·
              dados de {formatDateTime(metrics.data.generatedAt)}
            </p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div role="group" aria-label="Exportar métricas" className="flex items-center gap-1">
            <span className="text-sm text-muted-foreground">Exportar:</span>
            {(Object.keys(exportFormatLabels) as ExportFormat[]).map((format) => (
              <Button
                key={format}
                variant="outline"
                size="sm"
                disabled={exporter.isPending}
                aria-label={`Exportar ${exportFormatLabels[format]}`}
                onClick={() => exporter.mutate({ format, params })}
              >
                {exportFormatLabels[format]}
              </Button>
            ))}
          </div>
          {canSnapshot && (
            <Button
              variant="outline"
              disabled={snapshot.isPending}
              onClick={() => snapshot.mutate()}
            >
              Gravar snapshot de hoje
            </Button>
          )}
        </div>
      </div>
      {exporter.isPending && (
        <p className="text-sm text-muted-foreground" role="status">
          A gerar a exportação…
        </p>
      )}
      {exporter.isError && (
        <Alert variant="destructive">
          <AlertDescription>
            {exporter.error instanceof ApiError
              ? exporter.error.message
              : 'Não foi possível exportar as métricas.'}
          </AlertDescription>
        </Alert>
      )}
      {snapshot.isSuccess && (
        <Alert>
          <AlertDescription>Snapshot de hoje gravado.</AlertDescription>
        </Alert>
      )}
      <Filters metrics={metrics.data} params={params} onChange={setParams} />
      {invalid && (
        <Alert variant="destructive">
          <AlertDescription>{invalid}</AlertDescription>
        </Alert>
      )}
      {metrics.isError && !invalid && (
        <Alert variant="destructive">
          <AlertDescription>Não foi possível carregar as métricas.</AlertDescription>
        </Alert>
      )}
      {metrics.isPending && <p className="text-muted-foreground">A carregar…</p>}
      {metrics.data && !metrics.isError && <Metrics metrics={metrics.data} />}
    </div>
  )
}
