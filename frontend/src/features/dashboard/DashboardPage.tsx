import { useQuery } from '@tanstack/react-query'
import { lazy, Suspense, type ReactNode } from 'react'
import { Link } from 'react-router'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { IssueTable, KpiGrid, Section } from '@/features/analytics/AnalyticsShared'
import { formatNumber, formatPercent } from '@/features/analytics/format'
import { useDashboardOverview } from '@/features/analytics/useAnalytics'
import { useCurrentUser } from '@/features/auth/useAuth'
import { hasPermission } from '@/hooks/usePermissions'
import type { AlertGroup, DashboardOverview } from '@/services/analytics'
import { formatDate } from '@/services/common'
import { getHealth } from '@/services/health'

// Os gráficos (Recharts) ficam fora do bundle inicial.
const DashboardCharts = lazy(() => import('@/features/analytics/AnalyticsCharts'))

type Profile = 'management' | 'quality' | 'delivery'

const profileLabels: Record<Profile, string> = {
  management: 'Visão de gestão: alertas e sprints primeiro.',
  quality: 'Visão de qualidade: bugs críticos e testes primeiro.',
  delivery: 'Visão de equipa: o seu trabalho primeiro.',
}

const alertSinceLabels: Record<AlertGroup['kind'], string> = {
  blocked: 'Bloqueada há',
  stale: 'Sem atualização há',
  unassigned_critical_bugs: 'Aberto há',
}

function HealthCard() {
  const health = useQuery({ queryKey: ['health'], queryFn: getHealth })
  return (
    <Card className="max-w-sm">
      <CardHeader>
        <CardTitle>Estado da API</CardTitle>
        <CardDescription>Ligação ao backend VCCTeamForge</CardDescription>
      </CardHeader>
      <CardContent>
        {health.isPending && <p>A verificar…</p>}
        {health.isError && <p className="text-destructive">API indisponível</p>}
        {health.isSuccess && (
          <p>
            {health.data.status === 'ok' ? 'Operacional' : 'Com problemas'} · v{health.data.version}
          </p>
        )}
      </CardContent>
    </Card>
  )
}

function ActiveSprints({ overview }: { overview: DashboardOverview }) {
  return (
    <Section title="Sprints ativos">
      {overview.activeSprints.length === 0 ? (
        <p className="text-sm text-muted-foreground">Não há sprints ativos.</p>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {overview.activeSprints.map((sprint) => (
            <Card key={sprint.sprintId} size="sm">
              <CardHeader>
                <CardTitle>
                  <Link
                    className="hover:underline"
                    to={`/projects/${sprint.projectId}/sprints/${sprint.sprintId}/dashboard`}
                  >
                    {sprint.projectKey} · {sprint.name}
                  </Link>
                </CardTitle>
                {sprint.goal && <CardDescription>{sprint.goal}</CardDescription>}
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <div
                  className="h-2 rounded bg-muted"
                  role="progressbar"
                  aria-label={`Progresso de ${sprint.name}`}
                  aria-valuenow={sprint.progressPercent ?? 0}
                  aria-valuemin={0}
                  aria-valuemax={100}
                >
                  <span
                    className="block h-2 rounded bg-primary"
                    style={{ width: `${Math.min(sprint.progressPercent ?? 0, 100)}%` }}
                  />
                </div>
                <p className="text-muted-foreground">
                  {formatPercent(sprint.progressPercent)} ·{' '}
                  {formatNumber(sprint.completedStoryPoints)} de {formatNumber(sprint.storyPoints)}{' '}
                  SP · {sprint.completedIssueCount} de {sprint.issueCount} issues
                </p>
                <p>
                  Termina a {formatDate(sprint.endDate)} ({sprint.remainingDays}{' '}
                  {sprint.remainingDays === 1 ? 'dia' : 'dias'})
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </Section>
  )
}

function Alerts({ alerts }: { alerts: AlertGroup[] }) {
  return (
    <Section title="Alertas">
      <div className="space-y-4">
        {alerts.map((group) => (
          <div key={group.kind} className="space-y-1">
            <h4 className="font-medium">
              {group.label} <span className="text-muted-foreground">({group.total})</span>
            </h4>
            <IssueTable
              issues={group.issues}
              sinceLabel={alertSinceLabels[group.kind]}
              empty="Sem ocorrências."
            />
          </div>
        ))}
      </div>
    </Section>
  )
}

function MyWork({ overview }: { overview: DashboardOverview }) {
  const { myWork } = overview
  return (
    <Section
      title="O meu trabalho"
      description={`${myWork.openCount} por concluir · ${myWork.inProgressCount} em progresso · ${myWork.blockedCount} bloqueadas`}
    >
      <IssueTable
        issues={myWork.issues}
        sinceLabel="Atualizada há"
        empty="Não tem issues atribuídas por concluir."
      />
    </Section>
  )
}

function Overview({ overview, profile }: { overview: DashboardOverview; profile: Profile }) {
  const qualityAlerts = [...overview.alerts].sort(
    (a, b) =>
      Number(b.kind === 'unassigned_critical_bugs') - Number(a.kind === 'unassigned_critical_bugs'),
  )
  const blocks: Record<string, ReactNode> = {
    sprints: <ActiveSprints key="sprints" overview={overview} />,
    alerts: (
      <Alerts key="alerts" alerts={profile === 'quality' ? qualityAlerts : overview.alerts} />
    ),
    mine: <MyWork key="mine" overview={overview} />,
  }
  const order = {
    management: ['alerts', 'sprints', 'mine'],
    quality: ['alerts', 'mine', 'sprints'],
    delivery: ['mine', 'sprints', 'alerts'],
  }[profile]

  return (
    <>
      <p className="text-sm text-muted-foreground">
        {profileLabels[profile]} {overview.projectCount}{' '}
        {overview.projectCount === 1 ? 'projeto' : 'projetos'} ativos.
      </p>
      <KpiGrid kpis={overview.kpis} />
      {order.map((key) => blocks[key])}
      <Suspense fallback={<p className="text-muted-foreground">A carregar gráficos…</p>}>
        <DashboardCharts breakdown={overview.statusBreakdown} trend={overview.trend} />
      </Suspense>
    </>
  )
}

export function DashboardPage() {
  const { data: user } = useCurrentUser()
  const canRead = hasPermission(user, 'reports:read')
  const overview = useDashboardOverview(canRead)
  const profile: Profile =
    hasPermission(user, 'sprints:manage') || hasPermission(user, 'projects:manage')
      ? 'management'
      : hasPermission(user, 'tests:execute')
        ? 'quality'
        : 'delivery'

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Dashboard</h1>
      {canRead && overview.isPending && <p className="text-muted-foreground">A carregar…</p>}
      {canRead && overview.isError && (
        <Alert variant="destructive">
          <AlertDescription>Não foi possível carregar o dashboard.</AlertDescription>
        </Alert>
      )}
      {overview.isSuccess && <Overview overview={overview.data} profile={profile} />}
      <HealthCard />
    </div>
  )
}
