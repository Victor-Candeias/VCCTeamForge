import { Link } from 'react-router'

import { Alert, AlertDescription } from '@/components/ui/alert'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { IssueStatusBadge } from '@/features/issues/IssueBadges'
import { useSprintCommitment } from '@/features/sprints/useSprints'
import { formatDateTime } from '@/services/common'
import type { Sprint } from '@/services/sprints'

function points(value: number | null) {
  return value === null ? '—' : value.toLocaleString('pt-PT', { maximumFractionDigits: 1 })
}

/** Compromisso congelado no início do sprint e alterações de âmbito desde então. */
export function SprintCommitment({ sprint }: { sprint: Sprint }) {
  const commitment = useSprintCommitment(sprint.id, sprint.startedAt !== null)

  if (sprint.startedAt === null) return null
  if (commitment.isPending) return <p className="text-muted-foreground">A carregar…</p>
  if (commitment.isError) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Não foi possível carregar o compromisso do sprint.</AlertDescription>
      </Alert>
    )
  }

  const data = commitment.data
  return (
    <section className="space-y-2">
      <h3 className="text-lg font-semibold">Compromisso</h3>
      <p className="text-sm text-muted-foreground">
        Iniciado em {formatDateTime(data.takenAt)}: {data.issueCount} issues, {points(data.storyPoints)}{' '}
        story points
        {data.unestimatedCount > 0 && ` (${data.unestimatedCount} sem estimativa)`}. Desde então:{' '}
        {data.addedCount} adicionadas ({points(data.addedStoryPoints)} SP) e {data.removedCount}{' '}
        retiradas.
      </p>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-24">Chave</TableHead>
            <TableHead>Título</TableHead>
            <TableHead>No início</TableHead>
            <TableHead>Agora</TableHead>
            <TableHead className="w-28">SP (início → agora)</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.issues.map((issue) => (
            <TableRow key={issue.issueId} className={issue.inSprint ? undefined : 'opacity-60'}>
              <TableCell>
                <Link className="font-mono hover:underline" to={`/issues/${issue.key}`}>
                  {issue.key}
                </Link>
              </TableCell>
              <TableCell>
                {issue.title}
                {!issue.inSprint && (
                  <span className="ml-2 text-xs text-muted-foreground">(retirada)</span>
                )}
              </TableCell>
              <TableCell>
                <IssueStatusBadge status={issue.status} />
              </TableCell>
              <TableCell>
                {issue.currentStatus ? <IssueStatusBadge status={issue.currentStatus} /> : '—'}
              </TableCell>
              <TableCell>
                {points(issue.storyPoints)} → {points(issue.currentStoryPoints)}
              </TableCell>
            </TableRow>
          ))}
          {data.added.map((issue) => (
            <TableRow key={issue.issueId}>
              <TableCell>
                <Link className="font-mono hover:underline" to={`/issues/${issue.key}`}>
                  {issue.key}
                </Link>
              </TableCell>
              <TableCell>
                {issue.title}
                <span className="ml-2 text-xs text-muted-foreground">(adicionada)</span>
              </TableCell>
              <TableCell>—</TableCell>
              <TableCell>
                <IssueStatusBadge status={issue.status} />
              </TableCell>
              <TableCell>— → {points(issue.storyPoints)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </section>
  )
}
