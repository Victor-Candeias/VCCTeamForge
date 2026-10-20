import { useState } from 'react'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { NativeSelect } from '@/components/ui/native-select'
import { IssueCard } from '@/features/issues/IssueCard'
import { moveErrorMessage, useBoard, useMoveIssueStatus } from '@/features/issues/useBoard'
import { useProjectContext } from '@/features/projects/projectContext'
import { usePermission } from '@/hooks/usePermissions'
import {
  issueStatusLabels,
  issueTransitions,
  issueTypeLabels,
  issueTypes,
  type BoardParams,
  type IssueStatus,
  type IssueSummary,
  type IssueType,
} from '@/services/issues'

export function BoardPage() {
  const { project } = useProjectContext()
  const canWrite = usePermission('issues:write') && project.status !== 'archived'
  const [type, setType] = useState<IssueType | ''>('')
  const [mine, setMine] = useState(false)
  const params: BoardParams = {
    assigneeId: mine ? ['me'] : undefined,
    type: type ? [type] : undefined,
  }
  const board = useBoard(project.id, params)
  const moveStatus = useMoveIssueStatus()
  // Estados otimistas até o quadro ser recarregado (revertidos em caso de erro).
  const [moved, setMoved] = useState<Record<string, IssueStatus>>({})
  const [dragging, setDragging] = useState<IssueSummary | null>(null)
  const [error, setError] = useState<string | null>(null)

  const columns = board.data?.columns ?? []
  const all = columns.flatMap((column) => column.items)
  const statusOf = (issue: IssueSummary) => moved[issue.id] ?? issue.status

  function moveTo(issue: IssueSummary, status: IssueStatus) {
    const current = statusOf(issue)
    if (status === current) return
    if (!issueTransitions[current].includes(status)) {
      setError(
        `Transição não permitida: ${issueStatusLabels[current]} → ${issueStatusLabels[status]}.`,
      )
      return
    }
    setError(null)
    setMoved((previous) => ({ ...previous, [issue.id]: status }))
    moveStatus.mutate(
      { issueId: issue.id, status, version: issue.version },
      {
        onError: (mutationError) => setError(moveErrorMessage(mutationError)),
        onSettled: () =>
          setMoved((previous) => {
            const next = { ...previous }
            delete next[issue.id]
            return next
          }),
      },
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-4">
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
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={mine}
            onChange={(event) => setMine(event.target.checked)}
          />
          Só as minhas
        </label>
      </div>
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {board.isError && (
        <Alert variant="destructive">
          <AlertDescription>Não foi possível carregar o quadro.</AlertDescription>
        </Alert>
      )}
      {board.isPending && <p className="text-muted-foreground">A carregar…</p>}
      {board.data && (
        <div className="grid auto-cols-[minmax(16rem,1fr)] grid-flow-col gap-4 overflow-x-auto pb-2">
          {columns.map((column) => {
            const items = [
              ...column.items.filter((issue) => statusOf(issue) === column.status),
              ...all.filter(
                (issue) => issue.status !== column.status && moved[issue.id] === column.status,
              ),
            ]
            const total = column.total + items.length - column.items.length
            const label = issueStatusLabels[column.status]
            return (
              <section
                key={column.status}
                aria-label={label}
                className="space-y-2 rounded-lg bg-muted/50 p-2"
                onDragOver={(event) => event.preventDefault()}
                onDrop={(event) => {
                  event.preventDefault()
                  if (dragging) moveTo(dragging, column.status)
                  setDragging(null)
                }}
              >
                <h2 className="flex items-center justify-between px-1 text-sm font-semibold">
                  {label}
                  <span className="text-muted-foreground" aria-label={`${total} issues`}>
                    {total}
                  </span>
                </h2>
                {column.status === 'done' && (
                  <p className="px-1 text-xs text-muted-foreground">
                    Últimos {board.data.doneWindowDays} dias
                  </p>
                )}
                {column.truncated && (
                  <p className="px-1 text-xs text-muted-foreground">
                    A mostrar {board.data.columnLimit} de {column.total}; use os filtros.
                  </p>
                )}
                {items.map((issue) => (
                  <IssueCard
                    key={issue.id}
                    issue={issue}
                    draggable={canWrite}
                    onDragStart={(event) => {
                      setDragging(issue)
                      event.dataTransfer?.setData('text/plain', issue.id)
                    }}
                    actions={
                      canWrite && (
                        <NativeSelect
                          aria-label={`Mover ${issue.key} para`}
                          className="h-7 w-auto"
                          value=""
                          disabled={issue.id in moved}
                          onChange={(event) => moveTo(issue, event.target.value as IssueStatus)}
                        >
                          <option value="">Mover para…</option>
                          {issueTransitions[statusOf(issue)].map((status) => (
                            <option key={status} value={status}>
                              {issueStatusLabels[status]}
                            </option>
                          ))}
                        </NativeSelect>
                      )
                    }
                  />
                ))}
              </section>
            )
          })}
        </div>
      )}
    </div>
  )
}
