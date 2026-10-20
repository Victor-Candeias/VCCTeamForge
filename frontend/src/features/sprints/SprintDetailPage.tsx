import { useState, type ReactNode } from 'react'
import { Link, useParams } from 'react-router'

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
import { BlockedBadge, IssueStatusBadge, IssueTypeBadge } from '@/features/issues/IssueBadges'
import { useIssues } from '@/features/issues/useIssues'
import { useProjectContext } from '@/features/projects/projectContext'
import { EstimateInput } from '@/features/sprints/EstimateInput'
import { SprintCommitment } from '@/features/sprints/SprintCommitment'
import { SprintStatusBadge } from '@/features/sprints/SprintsPage'
import {
  useAddSprintIssues,
  useRemoveSprintIssue,
  useSprint,
  useStartSprint,
} from '@/features/sprints/useSprints'
import { usePermission } from '@/hooks/usePermissions'
import { mutationErrorMessage } from '@/lib/errors'
import { formatDate } from '@/services/common'
import { issueTypes, type IssueStatus, type IssueSummary } from '@/services/issues'
import type { Sprint } from '@/services/sprints'

const PLANNABLE_STATUSES: IssueStatus[] = ['todo', 'in_progress', 'code_review', 'testing']
const PLANNABLE_TYPES = issueTypes.filter((type) => type !== 'epic')
const LIST_LIMIT = 100

function formatPoints(value: number) {
  return value.toLocaleString('pt-PT', { maximumFractionDigits: 1 })
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
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

function PlanningTotals({ sprint }: { sprint: Sprint }) {
  const { scope, capacityStoryPoints: capacity } = sprint
  const overCapacity = capacity !== null && scope.storyPoints > capacity
  return (
    <div className="space-y-2">
      <div className="grid gap-3 sm:grid-cols-4">
        <Stat label="Issues" value={String(scope.issueCount)} />
        <Stat
          label="Story points"
          value={formatPoints(scope.storyPoints)}
          hint={capacity !== null ? `Capacidade: ${formatPoints(capacity)}` : 'Sem capacidade definida'}
        />
        <Stat label="Sem estimativa" value={String(scope.unestimatedCount)} />
        <Stat
          label="Concluídas"
          value={`${scope.completedIssueCount} / ${scope.issueCount}`}
          hint={`${formatPoints(scope.completedStoryPoints)} story points`}
        />
      </div>
      {overCapacity && (
        <Alert>
          <AlertDescription>
            O planeamento excede a capacidade do sprint em{' '}
            {formatPoints(scope.storyPoints - (capacity ?? 0))} story points.
          </AlertDescription>
        </Alert>
      )}
    </div>
  )
}

function IssueRows({
  issues,
  canPlan,
  canEstimate,
  action,
}: {
  issues: IssueSummary[]
  canPlan: boolean
  canEstimate: boolean
  action: (issue: IssueSummary) => ReactNode
}) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-24">Chave</TableHead>
          <TableHead>Título</TableHead>
          <TableHead>Tipo</TableHead>
          <TableHead>Estado</TableHead>
          <TableHead>Responsável</TableHead>
          <TableHead className="w-24">SP</TableHead>
          {canPlan && <TableHead className="w-28" />}
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
            <TableCell>
              <span className="mr-2">{issue.title}</span>
              {issue.blocked && <BlockedBadge />}
            </TableCell>
            <TableCell>
              <IssueTypeBadge type={issue.type} />
            </TableCell>
            <TableCell>
              <IssueStatusBadge status={issue.status} />
            </TableCell>
            <TableCell>{issue.assignee?.name ?? '—'}</TableCell>
            <TableCell>
              {canEstimate ? (
                <EstimateInput key={`${issue.id}-${issue.version}`} issue={issue} />
              ) : (
                (issue.storyPoints ?? '—')
              )}
            </TableCell>
            {canPlan && <TableCell>{action(issue)}</TableCell>}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

function StartSprint({ sprint }: { sprint: Sprint }) {
  const [confirming, setConfirming] = useState(false)
  const start = useStartSprint(sprint.id)
  const empty = sprint.scope.issueCount === 0

  if (!confirming) {
    return (
      <div className="space-y-1 text-right">
        <Button disabled={empty} onClick={() => setConfirming(true)}>
          Iniciar sprint
        </Button>
        {empty && (
          <p className="text-xs text-muted-foreground">Associe issues antes de iniciar.</p>
        )}
      </div>
    )
  }
  return (
    <div className="max-w-md space-y-2 rounded-lg border p-3" role="group" aria-label="Iniciar sprint">
      <p className="text-sm">
        O compromisso fica registado com {sprint.scope.issueCount} issues e{' '}
        {formatPoints(sprint.scope.storyPoints)} story points
        {sprint.scope.unestimatedCount > 0 &&
          ` (${sprint.scope.unestimatedCount} sem estimativa contam como 0)`}
        .
      </p>
      {start.error && (
        <Alert variant="destructive">
          <AlertDescription>{mutationErrorMessage(start.error)}</AlertDescription>
        </Alert>
      )}
      <div className="flex justify-end gap-2">
        <Button variant="outline" disabled={start.isPending} onClick={() => setConfirming(false)}>
          Cancelar
        </Button>
        <Button
          disabled={start.isPending}
          onClick={() => start.mutate(sprint.version, { onSuccess: () => setConfirming(false) })}
        >
          {start.isPending ? 'A iniciar…' : 'Confirmar início'}
        </Button>
      </div>
    </div>
  )
}

function SprintPlanning({ sprint }: { sprint: Sprint }) {
  const { project } = useProjectContext()
  const canPlan = sprint.canEdit
  const canEstimate = usePermission('issues:write') && project.status !== 'archived'
  const sprintIssues = useIssues({
    projectId: project.id,
    sprintId: sprint.id,
    sort: 'rank',
    pageSize: LIST_LIMIT,
  })
  const backlog = useIssues(
    {
      projectId: project.id,
      sprintId: 'none',
      status: PLANNABLE_STATUSES,
      type: PLANNABLE_TYPES,
      sort: 'rank',
      pageSize: LIST_LIMIT,
    },
    canPlan,
  )
  const add = useAddSprintIssues(sprint.id)
  const remove = useRemoveSprintIssue(sprint.id)
  const busy = add.isPending || remove.isPending
  const error = add.error ?? remove.error

  return (
    <div className="space-y-6">
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{mutationErrorMessage(error)}</AlertDescription>
        </Alert>
      )}
      <section className="space-y-2">
        <h3 className="text-lg font-semibold">Issues do sprint</h3>
        {sprintIssues.isError && (
          <Alert variant="destructive">
            <AlertDescription>Não foi possível carregar as issues do sprint.</AlertDescription>
          </Alert>
        )}
        {sprintIssues.data?.items.length === 0 && (
          <p className="text-muted-foreground">O sprint ainda não tem issues.</p>
        )}
        {sprintIssues.data && sprintIssues.data.items.length > 0 && (
          <IssueRows
            issues={sprintIssues.data.items}
            canPlan={canPlan}
            canEstimate={canEstimate}
            action={(issue) => (
              <Button
                variant="ghost"
                size="sm"
                disabled={busy}
                aria-label={`Remover ${issue.key} do sprint`}
                onClick={() => remove.mutate(issue.id)}
              >
                Remover
              </Button>
            )}
          />
        )}
      </section>

      {canPlan && (
        <section className="space-y-2">
          <h3 className="text-lg font-semibold">Backlog</h3>
          {backlog.isError && (
            <Alert variant="destructive">
              <AlertDescription>Não foi possível carregar o backlog.</AlertDescription>
            </Alert>
          )}
          {backlog.data?.items.length === 0 && (
            <p className="text-muted-foreground">Não há issues por planear.</p>
          )}
          {backlog.data && backlog.data.items.length > 0 && (
            <IssueRows
              issues={backlog.data.items}
              canPlan={canPlan}
              canEstimate={canEstimate}
              action={(issue) => (
                <Button
                  variant="outline"
                  size="sm"
                  disabled={busy}
                  aria-label={`Adicionar ${issue.key} ao sprint`}
                  onClick={() => add.mutate([issue.id])}
                >
                  Adicionar
                </Button>
              )}
            />
          )}
        </section>
      )}
    </div>
  )
}

export function SprintDetailPage() {
  const { project } = useProjectContext()
  const { sprintId = '' } = useParams()
  const sprint = useSprint(sprintId)

  if (sprint.isPending) return <p className="text-muted-foreground">A carregar…</p>
  if (sprint.isError || sprint.data.projectId !== project.id) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Sprint não encontrado ou sem acesso.</AlertDescription>
      </Alert>
    )
  }

  const data = sprint.data
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-semibold">{data.name}</h2>
            <SprintStatusBadge status={data.status} />
          </div>
          <p className="text-sm text-muted-foreground">
            {formatDate(data.startDate)} – {formatDate(data.endDate)} · {data.durationDays} dias
          </p>
          {data.goal && <p className="max-w-2xl">{data.goal}</p>}
        </div>
        <div className="flex flex-wrap items-start gap-2">
          {data.canEdit && data.status === 'planned' && <StartSprint sprint={data} />}
          {data.status === 'active' && (
            <Button variant="outline" asChild>
              <Link to={`/projects/${project.id}/board?sprintId=${data.id}`}>Ver quadro</Link>
            </Button>
          )}
          {data.canEdit && (
            <Button variant="outline" asChild>
              <Link to={`/projects/${project.id}/sprints/${data.id}/edit`}>Editar</Link>
            </Button>
          )}
          <Button variant="ghost" asChild>
            <Link to={`/projects/${project.id}/sprints`}>Voltar</Link>
          </Button>
        </div>
      </div>
      <PlanningTotals sprint={data} />
      <SprintCommitment sprint={data} />
      <SprintPlanning sprint={data} />
    </div>
  )
}
