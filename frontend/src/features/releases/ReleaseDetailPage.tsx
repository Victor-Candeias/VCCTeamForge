import { useState } from 'react'
import { Link, useParams } from 'react-router'

import { Markdown } from '@/components/Markdown'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { IssueStatusBadge } from '@/features/issues/IssueBadges'
import { useProjectContext } from '@/features/projects/projectContext'
import { ReleaseStatusBadge } from '@/features/releases/ReleaseShared'
import { useRelease, useTransitionRelease, useUpdateRelease } from '@/features/releases/useReleases'
import { TestPlanStatusBadge } from '@/features/testing/TestingShared'
import { mutationErrorMessage } from '@/lib/errors'
import { formatDate, formatDateTime } from '@/services/common'
import type { IssueRef } from '@/services/issues'
import {
  checklistInput,
  releaseHistoryLabels,
  releaseStatusLabels,
  type Release,
  type ReleaseStatus,
} from '@/services/releases'
import { formatPassRate } from '@/services/testing'

function transitionLabel(from: ReleaseStatus, to: ReleaseStatus): string {
  if (to === 'ready_for_qa') return 'Enviar para QA'
  if (to === 'approved') return 'Aprovar'
  if (to === 'released') return 'Publicar'
  return from === 'ready_for_qa' ? 'Rejeitar' : 'Reabrir'
}

function IssueList({ issues, empty }: { issues: IssueRef[]; empty: string }) {
  if (issues.length === 0) return <p className="text-sm text-muted-foreground">{empty}</p>
  return (
    <ul className="space-y-1">
      {issues.map((issue) => (
        <li key={issue.id} className="flex items-center gap-2 text-sm">
          <Link className="hover:underline" to={`/issues/${issue.key}`}>
            {issue.key} · {issue.title}
          </Link>
          <IssueStatusBadge status={issue.status} />
        </li>
      ))}
    </ul>
  )
}

function Transitions({ release }: { release: Release }) {
  const mutation = useTransitionRelease(release.id)
  const [comment, setComment] = useState('')
  const [commentError, setCommentError] = useState<string>()

  if (release.availableTransitions.length === 0) return null

  const run = (to: ReleaseStatus) => {
    if (to === 'draft' && !comment.trim()) {
      setCommentError('Indique o motivo')
      return
    }
    setCommentError(undefined)
    mutation.mutate(
      { to, comment: comment.trim(), version: release.version },
      { onSuccess: () => setComment('') },
    )
  }

  return (
    <section aria-labelledby="release-workflow" className="space-y-2">
      <h3 id="release-workflow" className="font-medium">
        Workflow
      </h3>
      {mutation.error && (
        <Alert variant="destructive">
          <AlertDescription>{mutationErrorMessage(mutation.error)}</AlertDescription>
        </Alert>
      )}
      <div className="max-w-xl space-y-1.5">
        <Label htmlFor="release-comment">Comentário</Label>
        <Textarea
          id="release-comment"
          rows={2}
          maxLength={2000}
          value={comment}
          onChange={(event) => setComment(event.target.value)}
        />
        {commentError && <p className="text-sm text-destructive">{commentError}</p>}
      </div>
      <div className="flex flex-wrap gap-2">
        {release.availableTransitions.map((to) => (
          <Button
            key={to}
            type="button"
            variant={to === 'draft' ? 'outline' : 'default'}
            disabled={mutation.isPending}
            onClick={() => run(to)}
          >
            {transitionLabel(release.status, to)}
          </Button>
        ))}
      </div>
    </section>
  )
}

function Checklist({ release }: { release: Release }) {
  const mutation = useUpdateRelease(release.id)

  const toggle = (itemId: string, done: boolean) =>
    mutation.mutate({
      version: release.version,
      checklist: checklistInput(release.checklist).map((item) =>
        item.id === itemId ? { ...item, done } : item,
      ),
    })

  return (
    <section aria-labelledby="release-checklist-detail" className="space-y-2">
      <h3 id="release-checklist-detail" className="font-medium">
        Checklist ({release.checklistDone}/{release.checklistTotal})
      </h3>
      {mutation.error && (
        <Alert variant="destructive">
          <AlertDescription>{mutationErrorMessage(mutation.error)}</AlertDescription>
        </Alert>
      )}
      {release.checklist.length === 0 && (
        <p className="text-sm text-muted-foreground">Sem itens na checklist.</p>
      )}
      <ul className="space-y-1">
        {release.checklist.map((item) => (
          <li key={item.id} className="flex flex-wrap items-center gap-2 text-sm">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={item.done}
                disabled={!release.canEdit || mutation.isPending}
                onChange={(event) => toggle(item.id, event.target.checked)}
              />
              {item.label}
            </label>
            {item.required && <span className="text-xs text-muted-foreground">(obrigatório)</span>}
            {item.done && item.doneBy && (
              <span className="text-xs text-muted-foreground">
                {item.doneBy.name} · {formatDateTime(item.doneAt)}
              </span>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}

function Quality({ release }: { release: Release }) {
  const { quality } = release
  return (
    <section aria-labelledby="release-quality" className="space-y-2">
      <h3 id="release-quality" className="font-medium">
        Qualidade
      </h3>
      <dl className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
        <div>
          <dt className="inline text-muted-foreground">Issues concluídas: </dt>
          <dd className="inline">
            {quality.issues.done}/{quality.issues.total}
          </dd>
        </div>
        <div>
          <dt className="inline text-muted-foreground">Bugs conhecidos em aberto: </dt>
          <dd className="inline">
            {quality.knownBugs.open} ({quality.knownBugs.openCritical} críticos)
          </dd>
        </div>
        <div>
          <dt className="inline text-muted-foreground">Casos executados: </dt>
          <dd className="inline">
            {quality.tests.executedCases}/{quality.tests.totalCases}
          </dd>
        </div>
        <div>
          <dt className="inline text-muted-foreground">Pass rate: </dt>
          <dd className="inline">{formatPassRate(quality.tests.passRate)}</dd>
        </div>
        <div>
          <dt className="inline text-muted-foreground">Regressões: </dt>
          <dd className="inline">{quality.tests.regressions}</dd>
        </div>
      </dl>
      <ul aria-label="Critérios de aprovação" className="space-y-1 text-sm">
        {quality.criteria.map((criterion) => (
          <li key={criterion.key} className={criterion.enabled ? '' : 'text-muted-foreground'}>
            <span aria-hidden>{!criterion.enabled ? '–' : criterion.passed ? '✓' : '✗'}</span>{' '}
            {criterion.label}: {criterion.detail}
            {!criterion.enabled
              ? ' (não exigido)'
              : criterion.passed
                ? ' (cumprido)'
                : ' (por cumprir)'}
          </li>
        ))}
      </ul>
      <p className="text-sm font-medium">
        {quality.ready ? 'Pronta para aprovação' : 'Ainda não cumpre os requisitos de aprovação'}
      </p>
    </section>
  )
}

export function ReleaseDetailPage() {
  const { project } = useProjectContext()
  const { releaseId = '' } = useParams()
  const release = useRelease(releaseId)

  if (release.isPending) return <p className="text-muted-foreground">A carregar…</p>
  if (release.isError || release.data.projectId !== project.id) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Release não encontrada ou sem acesso.</AlertDescription>
      </Alert>
    )
  }
  const data = release.data

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-semibold">Release {data.name}</h2>
            <ReleaseStatusBadge status={data.status} />
          </div>
          <p className="text-sm text-muted-foreground">
            Data prevista: {formatDate(data.plannedDate)}
            {data.releasedAt && <> · Publicada em {formatDateTime(data.releasedAt)}</>}
          </p>
        </div>
        <div className="flex gap-2">
          {data.canEdit && (
            <Button asChild>
              <Link to={`/projects/${project.id}/releases/${data.id}/edit`}>Editar</Link>
            </Button>
          )}
          <Button variant="outline" asChild>
            <Link to={`/projects/${project.id}/releases`}>Voltar</Link>
          </Button>
        </div>
      </div>

      {data.description && <p className="whitespace-pre-wrap text-sm">{data.description}</p>}

      <Quality release={data} />
      <Checklist release={data} />
      <Transitions release={data} />

      <section aria-labelledby="release-issues-detail" className="space-y-2">
        <h3 id="release-issues-detail" className="font-medium">
          Issues incluídas
        </h3>
        <IssueList issues={data.issues} empty="Nenhuma issue incluída." />
      </section>
      <section aria-labelledby="release-bugs-detail" className="space-y-2">
        <h3 id="release-bugs-detail" className="font-medium">
          Bugs conhecidos
        </h3>
        <IssueList issues={data.knownBugs} empty="Nenhum bug conhecido." />
      </section>
      <section aria-labelledby="release-plans-detail" className="space-y-2">
        <h3 id="release-plans-detail" className="font-medium">
          Planos de teste
        </h3>
        {data.testPlans.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nenhum plano de teste associado.</p>
        ) : (
          <ul className="space-y-1">
            {data.testPlans.map((plan) => (
              <li key={plan.id} className="flex items-center gap-2 text-sm">
                <Link
                  className="hover:underline"
                  to={`/projects/${project.id}/tests/plans/${plan.id}`}
                >
                  {plan.name}
                </Link>
                <TestPlanStatusBadge status={plan.status} />
              </li>
            ))}
          </ul>
        )}
      </section>
      <section aria-labelledby="release-notes-detail" className="space-y-2">
        <h3 id="release-notes-detail" className="font-medium">
          Notas de release
        </h3>
        {data.notes ? (
          <Markdown>{data.notes}</Markdown>
        ) : (
          <p className="text-sm text-muted-foreground">Sem notas.</p>
        )}
      </section>
      <section aria-labelledby="release-history" className="space-y-2">
        <h3 id="release-history" className="font-medium">
          Histórico
        </h3>
        <ol className="space-y-1 text-sm">
          {data.history.map((entry, index) => (
            <li key={`${entry.at}-${index}`}>
              <span className="font-medium">
                {releaseHistoryLabels[entry.action] ?? entry.action}
              </span>
              {entry.fromStatus && entry.toStatus && (
                <>
                  {' '}
                  ({releaseStatusLabels[entry.fromStatus]} → {releaseStatusLabels[entry.toStatus]})
                </>
              )}
              {' · '}
              {entry.user?.name ?? 'Utilizador removido'} · {formatDateTime(entry.at)}
              {entry.fields.length > 0 && <> · {entry.fields.join(', ')}</>}
              {entry.comment && <p className="text-muted-foreground">“{entry.comment}”</p>}
            </li>
          ))}
        </ol>
      </section>
    </div>
  )
}
