import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router'

import { Field } from '@/components/Field'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { NativeSelect } from '@/components/ui/native-select'
import { Textarea } from '@/components/ui/textarea'
import { useProjectContext } from '@/features/projects/projectContext'
import { useCloseSprint, useSprint, useSprints } from '@/features/sprints/useSprints'
import { mutationErrorMessage } from '@/lib/errors'
import { ApiError } from '@/services/apiClient'
import { formatDate } from '@/services/common'
import type { Sprint, SprintRetrospective } from '@/services/sprints'

const RETROSPECTIVE_MAX_LENGTH = 5000
const BACKLOG = ''

const retrospectiveFields: { name: keyof SprintRetrospective; label: string }[] = [
  { name: 'wentWell', label: 'O que correu bem' },
  { name: 'toImprove', label: 'O que melhorar' },
  { name: 'actions', label: 'Ações' },
]

function formatPoints(value: number) {
  return value.toLocaleString('pt-PT', { maximumFractionDigits: 1 })
}

function CloseForm({ sprint }: { sprint: Sprint }) {
  const { project } = useProjectContext()
  const navigate = useNavigate()
  const close = useCloseSprint(sprint.id)
  const planned = useSprints({
    projectId: project.id,
    status: ['planned'],
    sort: 'startDate',
    pageSize: 50,
  })
  const [target, setTarget] = useState(BACKLOG)
  const [retrospective, setRetrospective] = useState<SprintRetrospective>({
    wentWell: '',
    toImprove: '',
    actions: '',
  })
  const { scope } = sprint
  const pendingCount = scope.issueCount - scope.completedIssueCount
  const pendingPoints = scope.storyPoints - scope.completedStoryPoints
  const serverErrors = close.error instanceof ApiError ? close.error.fieldErrors() : {}

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    close.mutate(
      { version: sprint.version, carryOverSprintId: target || null, retrospective },
      { onSuccess: () => void navigate(`/projects/${project.id}/sprints/${sprint.id}`) },
    )
  }

  return (
    <form className="max-w-2xl space-y-4" noValidate onSubmit={onSubmit}>
      {close.error && (
        <Alert variant="destructive">
          <AlertDescription>{mutationErrorMessage(close.error)}</AlertDescription>
        </Alert>
      )}
      <p>
        {scope.completedIssueCount} issues concluídas ({formatPoints(scope.completedStoryPoints)}{' '}
        story points) ficam no sprint. {pendingCount} issues por concluir (
        {formatPoints(pendingPoints)} story points) serão transportadas.
      </p>
      <Field
        label="Destino das issues por concluir"
        htmlFor="close-target"
        error={serverErrors.carryOverSprintId}
      >
        <NativeSelect
          id="close-target"
          value={target}
          onChange={(event) => setTarget(event.target.value)}
        >
          <option value={BACKLOG}>Backlog</option>
          {planned.data?.items.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name} ({formatDate(item.startDate)})
            </option>
          ))}
        </NativeSelect>
      </Field>
      <h3 className="text-lg font-semibold">Retrospetiva</h3>
      {retrospectiveFields.map(({ name, label }) => (
        <Field
          key={name}
          label={label}
          htmlFor={`close-${name}`}
          error={serverErrors[name]}
        >
          <Textarea
            id={`close-${name}`}
            rows={3}
            maxLength={RETROSPECTIVE_MAX_LENGTH}
            value={retrospective[name]}
            onChange={(event) =>
              setRetrospective((current) => ({ ...current, [name]: event.target.value }))
            }
          />
        </Field>
      ))}
      <div className="flex gap-2">
        <Button type="submit" disabled={close.isPending}>
          {close.isPending ? 'A fechar…' : 'Fechar sprint'}
        </Button>
        <Button variant="outline" asChild>
          <Link to={`/projects/${project.id}/sprints/${sprint.id}`}>Cancelar</Link>
        </Button>
      </div>
    </form>
  )
}

export function SprintClosePage() {
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
  if (sprint.data.status !== 'active' || !sprint.data.canEdit) {
    return (
      <Alert>
        <AlertDescription>Só é possível fechar um sprint ativo.</AlertDescription>
      </Alert>
    )
  }
  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">Fechar {sprint.data.name}</h2>
      <CloseForm sprint={sprint.data} />
    </div>
  )
}

/** Resultado e retrospetiva de um sprint fechado. */
export function SprintClosure({ sprint }: { sprint: Sprint }) {
  const { project } = useProjectContext()
  const { result, retrospective } = sprint
  const target = useSprint(result?.carryOverSprintId ?? '')
  if (!result) return null

  return (
    <section className="space-y-3">
      <h3 className="text-lg font-semibold">Resultado</h3>
      <div className="grid gap-3 sm:grid-cols-3">
        <Card size="sm">
          <CardHeader>
            <CardTitle className="text-sm text-muted-foreground">Concluídas</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold">{result.completedIssueCount}</p>
            <p className="text-xs text-muted-foreground">
              {formatPoints(result.completedStoryPoints)} story points
            </p>
          </CardContent>
        </Card>
        <Card size="sm">
          <CardHeader>
            <CardTitle className="text-sm text-muted-foreground">Do compromisso</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold">{result.committedCompletedIssueCount}</p>
            <p className="text-xs text-muted-foreground">
              {formatPoints(result.committedCompletedStoryPoints)} story points
            </p>
          </CardContent>
        </Card>
        <Card size="sm">
          <CardHeader>
            <CardTitle className="text-sm text-muted-foreground">Transportadas</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold">{result.carriedOverIssueCount}</p>
            <p className="text-xs text-muted-foreground">
              {formatPoints(result.carriedOverStoryPoints)} story points para{' '}
              {result.carryOverSprintId === null ? (
                'o backlog'
              ) : (
                <Link
                  className="hover:underline"
                  to={`/projects/${project.id}/sprints/${result.carryOverSprintId}`}
                >
                  {target.data?.name ?? 'o sprint seguinte'}
                </Link>
              )}
            </p>
          </CardContent>
        </Card>
      </div>
      {retrospective && (
        <dl className="space-y-2">
          {retrospectiveFields.map(({ name, label }) => (
            <div key={name}>
              <dt className="text-sm font-medium">{label}</dt>
              <dd className="whitespace-pre-wrap text-muted-foreground">
                {retrospective[name] || '—'}
              </dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  )
}
