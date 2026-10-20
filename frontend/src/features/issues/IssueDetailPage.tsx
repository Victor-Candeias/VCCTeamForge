import { useState, type ReactNode } from 'react'
import { Link, useParams } from 'react-router'

import { Markdown } from '@/components/Markdown'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { BlockedBadge, IssueStatusBadge, IssueTypeBadge } from '@/features/issues/IssueBadges'
import { IssueAttachments } from '@/features/issues/IssueAttachments'
import { IssueComments } from '@/features/issues/IssueComments'
import { IssueHistory } from '@/features/issues/IssueHistory'
import { useIssue, useUpdateIssue } from '@/features/issues/useIssues'
import { PriorityBadge } from '@/features/projects/ProjectBadges'
import { mutationErrorMessage } from '@/lib/errors'
import { formatDate, formatDateTime } from '@/services/common'
import { issueStatusLabels, type Issue } from '@/services/issues'

function BlockControls({ issue }: { issue: Issue }) {
  const mutation = useUpdateIssue(issue.id)
  const [editing, setEditing] = useState(false)
  const [reason, setReason] = useState('')

  if (issue.blocked) {
    return (
      <Button
        variant="outline"
        disabled={mutation.isPending}
        onClick={() => mutation.mutate({ version: issue.version, blocked: false })}
      >
        Desbloquear
      </Button>
    )
  }
  if (!editing) {
    return (
      <Button variant="outline" onClick={() => setEditing(true)}>
        Bloquear
      </Button>
    )
  }
  return (
    <form
      className="w-full space-y-2"
      onSubmit={(event) => {
        event.preventDefault()
        if (!reason.trim()) return
        mutation.mutate(
          { version: issue.version, blocked: true, blockReason: reason.trim() },
          { onSuccess: () => setEditing(false) },
        )
      }}
    >
      <Label htmlFor="block-reason">Motivo do bloqueio</Label>
      <Textarea
        id="block-reason"
        maxLength={500}
        value={reason}
        onChange={(event) => setReason(event.target.value)}
      />
      <div className="flex gap-2">
        <Button type="submit" disabled={!reason.trim() || mutation.isPending}>
          Confirmar bloqueio
        </Button>
        <Button type="button" variant="ghost" onClick={() => setEditing(false)}>
          Cancelar
        </Button>
      </div>
    </form>
  )
}

type ActivityTab = 'comments' | 'history'

function IssueActivity({ issue }: { issue: Issue }) {
  const [tab, setTab] = useState<ActivityTab>('comments')
  const tabs: [ActivityTab, string][] = [
    ['comments', 'Comentários'],
    ['history', 'Histórico'],
  ]
  return (
    <section className="space-y-3">
      <div role="tablist" aria-label="Atividade" className="flex gap-1 border-b">
        {tabs.map(([value, label]) => (
          <button
            key={value}
            type="button"
            role="tab"
            id={`tab-${value}`}
            aria-selected={tab === value}
            aria-controls={`panel-${value}`}
            className={`-mb-px border-b-2 px-3 py-2 text-sm ${
              tab === value
                ? 'border-primary font-medium'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
            onClick={() => setTab(value)}
          >
            {label}
          </button>
        ))}
      </div>
      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
        {tab === 'comments' ? (
          <IssueComments issueId={issue.id} />
        ) : (
          <IssueHistory issueId={issue.id} projectId={issue.projectId} />
        )}
      </div>
    </section>
  )
}

export function IssueDetailPage() {
  const { issueKey = '' } = useParams()
  const issue = useIssue(issueKey)
  const mutation = useUpdateIssue(issue.data?.id ?? '')

  if (issue.isPending) return <p className="text-muted-foreground">A carregar…</p>
  if (issue.isError) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Issue não encontrada ou sem acesso.</AlertDescription>
      </Alert>
    )
  }
  const data = issue.data
  const details: [string, ReactNode][] = [
    ['Estado', <IssueStatusBadge key="s" status={data.status} />],
    ['Prioridade', <PriorityBadge key="p" priority={data.priority} />],
    ['Responsável', data.assignee?.name ?? '—'],
    ['Reportada por', data.reporter?.name ?? '—'],
    ['Story points', data.storyPoints ?? '—'],
    ['Data limite', formatDate(data.dueDate)],
    [
      'Issue pai',
      data.parent ? (
        <Link key="parent" className="hover:underline" to={`/issues/${data.parent.key}`}>
          {data.parent.key} · {data.parent.title}
        </Link>
      ) : (
        '—'
      ),
    ],
    ['Criada', formatDateTime(data.createdAt)],
    ['Atualizada', formatDateTime(data.updatedAt)],
  ]

  return (
    <div className="space-y-4">
      <div className="text-sm text-muted-foreground">
        <Link className="hover:underline" to={`/projects/${data.projectId}/issues`}>
          {data.projectKey}
        </Link>{' '}
        / <span className="font-mono">{data.key}</span>
      </div>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-2">
          <h1 className="text-2xl font-semibold">{data.title}</h1>
          <div className="flex flex-wrap gap-2">
            <IssueTypeBadge type={data.type} />
            {data.blocked && <BlockedBadge />}
            {data.labels.map((label) => (
              <Badge key={label} variant="outline">
                {label}
              </Badge>
            ))}
          </div>
        </div>
        {data.canEdit && (
          <Button variant="outline" asChild>
            <Link to={`/issues/${data.key}/edit`}>Editar</Link>
          </Button>
        )}
      </div>

      {mutation.isError && (
        <Alert variant="destructive">
          <AlertDescription>{mutationErrorMessage(mutation.error)}</AlertDescription>
        </Alert>
      )}
      {data.blocked && (
        <Alert variant="destructive">
          <AlertTitle>Bloqueada</AlertTitle>
          <AlertDescription>{data.blockReason}</AlertDescription>
        </Alert>
      )}

      {data.canEdit && (
        <div className="flex flex-wrap items-center gap-2">
          {data.allowedTransitions.map((status) => (
            <Button
              key={status}
              variant="secondary"
              size="sm"
              disabled={mutation.isPending}
              onClick={() => mutation.mutate({ version: data.version, status })}
            >
              Mover para {issueStatusLabels[status]}
            </Button>
          ))}
          <BlockControls key={`${data.id}-${data.version}`} issue={data} />
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
        <div className="space-y-6">
          <section className="space-y-2">
            <h2 className="font-medium">Descrição</h2>
            {data.description ? (
              <Markdown>{data.description}</Markdown>
            ) : (
              <p className="text-sm text-muted-foreground">Sem descrição.</p>
            )}
          </section>
          {data.acceptanceCriteria.length > 0 && (
            <section className="space-y-2">
              <h2 className="font-medium">Critérios de aceitação</h2>
              <ul className="list-disc space-y-1 pl-5 text-sm">
                {data.acceptanceCriteria.map((criterion, index) => (
                  <li key={index}>{criterion}</li>
                ))}
              </ul>
            </section>
          )}
          {data.dependsOn.length > 0 && (
            <section className="space-y-2">
              <h2 className="font-medium">Depende de</h2>
              <ul className="space-y-1 text-sm">
                {data.dependsOn.map((dependency) => (
                  <li key={dependency.id}>
                    <Link className="hover:underline" to={`/issues/${dependency.key}`}>
                      {dependency.key} · {dependency.title}
                    </Link>{' '}
                    <IssueStatusBadge status={dependency.status} />
                  </li>
                ))}
              </ul>
            </section>
          )}
          <IssueAttachments issueId={data.id} />
          <IssueActivity issue={data} />
        </div>
        <dl className="grid h-fit grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
          {details.map(([label, value]) => (
            <div key={label} className="contents">
              <dt className="text-muted-foreground">{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      </div>
    </div>
  )
}
