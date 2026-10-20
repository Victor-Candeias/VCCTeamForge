import { useState, type FormEvent } from 'react'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { NativeSelect } from '@/components/ui/native-select'
import { IssueStatusBadge } from '@/features/issues/IssueBadges'
import { IssueCard } from '@/features/issues/IssueCard'
import { reorder } from '@/features/issues/ordering'
import { moveErrorMessage, useMoveIssueRank } from '@/features/issues/useBoard'
import { useCreateIssue, useIssues } from '@/features/issues/useIssues'
import { useProjectContext } from '@/features/projects/projectContext'
import { usePermission } from '@/hooks/usePermissions'
import { mutationErrorMessage } from '@/lib/errors'
import {
  issueTypeLabels,
  issueTypes,
  type IssueSearchParams,
  type IssueStatus,
  type IssueType,
} from '@/services/issues'

const BACKLOG_STATUSES: IssueStatus[] = ['todo', 'in_progress', 'code_review', 'testing']
const BACKLOG_LIMIT = 100
const QUICK_CREATE_TYPES = issueTypes.filter((type) => type !== 'epic' && type !== 'subtask')

export function BacklogPage() {
  const { project } = useProjectContext()
  const canWrite = usePermission('issues:write') && project.status !== 'archived'
  const [type, setType] = useState<IssueType | ''>('')
  const params: IssueSearchParams = {
    projectId: project.id,
    sprintId: 'none',
    status: BACKLOG_STATUSES,
    type: type ? [type] : undefined,
    sort: 'rank',
    pageSize: BACKLOG_LIMIT,
  }
  const issues = useIssues(params)
  const moveRank = useMoveIssueRank()
  const [order, setOrder] = useState<string[] | null>(null)
  const [dragging, setDragging] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const items = issues.data?.items ?? []
  const byId = new Map(items.map((issue) => [issue.id, issue]))
  const visible = order ? order.flatMap((id) => (byId.has(id) ? [byId.get(id)!] : [])) : items

  function move(issueId: string, to: number) {
    const issue = byId.get(issueId)
    const result = reorder(
      visible.map((item) => item.id),
      issueId,
      to,
    )
    if (!issue || !result || moveRank.isPending) return
    setError(null)
    setOrder(result.order)
    moveRank.mutate(
      {
        issueId,
        version: issue.version,
        afterId: result.afterId,
        beforeId: result.beforeId,
      },
      {
        onError: (mutationError) => setError(moveErrorMessage(mutationError)),
        onSettled: () => setOrder(null),
      },
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <label className="space-y-1 text-sm">
          <span className="block font-medium">Tipo</span>
          <NativeSelect
            value={type}
            onChange={(event) => setType(event.target.value as IssueType | '')}
          >
            <option value="">Todos os tipos</option>
            {issueTypes.map((value) => (
              <option key={value} value={value}>
                {issueTypeLabels[value]}
              </option>
            ))}
          </NativeSelect>
        </label>
        {canWrite && <QuickCreate projectId={project.id} />}
      </div>
      <p className="text-sm text-muted-foreground">
        Issues sem sprint e por concluir, pela ordem de prioridade da equipa
        {canWrite && ' (arraste ou use Topo/Subir/Descer para reordenar)'}.
      </p>
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {issues.isError && (
        <Alert variant="destructive">
          <AlertDescription>Não foi possível carregar o backlog.</AlertDescription>
        </Alert>
      )}
      {issues.isPending && <p className="text-muted-foreground">A carregar…</p>}
      {issues.data && items.length === 0 && (
        <p className="text-muted-foreground">O backlog está vazio.</p>
      )}
      <ol aria-label="Backlog" className="space-y-2">
        {visible.map((issue, index) => (
          <li key={issue.id}>
            <IssueCard
              issue={issue}
              draggable={canWrite}
              onDragStart={(event) => {
                setDragging(issue.id)
                event.dataTransfer?.setData('text/plain', issue.id)
              }}
              onDragOver={(event) => event.preventDefault()}
              onDrop={(event) => {
                event.preventDefault()
                if (dragging) move(dragging, index)
                setDragging(null)
              }}
              actions={
                <span className="flex items-center gap-1">
                  {issue.status !== 'todo' && <IssueStatusBadge status={issue.status} />}
                  {canWrite && (
                    <>
                      <Button
                        size="xs"
                        variant="ghost"
                        aria-label={`Mover ${issue.key} para o topo`}
                        disabled={index === 0 || moveRank.isPending}
                        onClick={() => move(issue.id, 0)}
                      >
                        Topo
                      </Button>
                      <Button
                        size="xs"
                        variant="ghost"
                        aria-label={`Subir ${issue.key}`}
                        disabled={index === 0 || moveRank.isPending}
                        onClick={() => move(issue.id, index - 1)}
                      >
                        Subir
                      </Button>
                      <Button
                        size="xs"
                        variant="ghost"
                        aria-label={`Descer ${issue.key}`}
                        disabled={index === visible.length - 1 || moveRank.isPending}
                        onClick={() => move(issue.id, index + 1)}
                      >
                        Descer
                      </Button>
                    </>
                  )}
                </span>
              }
            />
          </li>
        ))}
      </ol>
      {issues.data && issues.data.total > BACKLOG_LIMIT && (
        <p className="text-sm text-muted-foreground">
          A mostrar as primeiras {BACKLOG_LIMIT} de {issues.data.total} issues.
        </p>
      )}
    </div>
  )
}

function QuickCreate({ projectId }: { projectId: string }) {
  const create = useCreateIssue()
  const [title, setTitle] = useState('')
  const [type, setType] = useState<IssueType>('story')

  function submit(event: FormEvent) {
    event.preventDefault()
    if (!title.trim()) return
    create.mutate(
      {
        projectId,
        type,
        title: title.trim(),
        description: '',
        priority: 'medium',
        assigneeId: null,
        parentIssueId: null,
        storyPoints: null,
        labels: [],
        acceptanceCriteria: [],
        dueDate: null,
      },
      { onSuccess: () => setTitle('') },
    )
  }

  return (
    <form className="flex flex-wrap items-end gap-2" onSubmit={submit}>
      <NativeSelect
        aria-label="Tipo da nova issue"
        className="w-auto"
        value={type}
        onChange={(event) => setType(event.target.value as IssueType)}
      >
        {QUICK_CREATE_TYPES.map((value) => (
          <option key={value} value={value}>
            {issueTypeLabels[value]}
          </option>
        ))}
      </NativeSelect>
      <Input
        aria-label="Título da nova issue"
        className="w-64"
        maxLength={200}
        placeholder="Nova issue no fim do backlog"
        value={title}
        onChange={(event) => setTitle(event.target.value)}
      />
      <Button type="submit" disabled={create.isPending || !title.trim()}>
        Adicionar
      </Button>
      {create.isError && (
        <p role="alert" className="w-full text-sm text-destructive">
          {mutationErrorMessage(create.error)}
        </p>
      )}
    </form>
  )
}
