import { useState } from 'react'

import { Pagination } from '@/components/Pagination'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { useHistory } from '@/features/issues/useComments'
import { useProjectMembers } from '@/features/projects/useProjects'
import type { FieldChange, HistoryEvent } from '@/services/comments'
import { formatDate, formatDateTime, priorityLabels, type Priority } from '@/services/common'
import { issueStatusLabels, type IssueStatus } from '@/services/issues'

const fieldLabels: Record<string, string> = {
  title: 'Título',
  description: 'Descrição',
  status: 'Estado',
  priority: 'Prioridade',
  assigneeId: 'Responsável',
  parentIssueId: 'Issue pai',
  storyPoints: 'Story points',
  labels: 'Labels',
  acceptanceCriteria: 'Critérios de aceitação',
  dependsOnIssueIds: 'Dependências',
  dueDate: 'Data limite',
  blocked: 'Bloqueada',
  blockReason: 'Motivo do bloqueio',
  sprintId: 'Sprint',
  rank: 'Ordem',
}

// Campos cujo valor não é legível (IDs ou conteúdo longo): mostra-se apenas que mudaram.
const opaqueFields = new Set([
  'description',
  'acceptanceCriteria',
  'parentIssueId',
  'dependsOnIssueIds',
  'sprintId',
  'rank',
])

const eventLabels: Partial<Record<HistoryEvent['type'], string>> = {
  created: 'criou a issue',
  comment_added: 'comentou',
  comment_edited: 'editou um comentário',
  comment_deleted: 'removeu um comentário',
  attachment_added: 'adicionou um anexo',
  attachment_removed: 'removeu um anexo',
}

function formatValue(change: FieldChange, value: unknown, names: Map<string, string>): string {
  if (value === null || value === undefined || value === '') return '—'
  switch (change.field) {
    case 'status':
      return issueStatusLabels[value as IssueStatus] ?? String(value)
    case 'priority':
      return priorityLabels[value as Priority] ?? String(value)
    case 'assigneeId':
      return names.get(String(value)) ?? 'outro utilizador'
    case 'blocked':
      return value ? 'Sim' : 'Não'
    case 'dueDate':
      return formatDate(String(value).slice(0, 10))
    case 'labels':
      return Array.isArray(value) && value.length > 0 ? value.join(', ') : '—'
    default:
      return String(value)
  }
}

function ChangeLine({ change, names }: { change: FieldChange; names: Map<string, string> }) {
  const label = fieldLabels[change.field] ?? change.field
  if (opaqueFields.has(change.field)) return <li>alterou {label}</li>
  return (
    <li>
      alterou {label} de <strong>{formatValue(change, change.from, names)}</strong> para{' '}
      <strong>{formatValue(change, change.to, names)}</strong>
    </li>
  )
}

export function IssueHistory({ issueId, projectId }: { issueId: string; projectId: string }) {
  const [page, setPage] = useState(1)
  const history = useHistory(issueId, page)
  const members = useProjectMembers(projectId)
  const names = new Map((members.data?.members ?? []).map((member) => [member.id, member.name]))

  if (history.isPending) return <p className="text-muted-foreground">A carregar…</p>
  if (history.isError) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Não foi possível carregar o histórico.</AlertDescription>
      </Alert>
    )
  }
  return (
    <div className="space-y-4">
      <ol className="space-y-3 border-l pl-4">
        {history.data.items.map((event) => {
          const actor = event.actor?.name ?? 'Utilizador removido'
          return (
            <li key={event.id} className="text-sm">
              <div className="text-muted-foreground">{formatDateTime(event.createdAt)}</div>
              {event.type === 'updated' ? (
                <div>
                  <span className="font-medium">{actor}</span>
                  <ul className="list-disc pl-5">
                    {event.changes.map((change) => (
                      <ChangeLine key={change.field} change={change} names={names} />
                    ))}
                  </ul>
                </div>
              ) : (
                <div>
                  <span className="font-medium">{actor}</span> {eventLabels[event.type] ?? event.type}
                </div>
              )}
            </li>
          )
        })}
      </ol>
      {history.data.total > history.data.pageSize && (
        <Pagination
          page={history.data.page}
          pageSize={history.data.pageSize}
          total={history.data.total}
          onChange={setPage}
        />
      )}
    </div>
  )
}
