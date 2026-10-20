import { useState } from 'react'
import { Link } from 'react-router'

import { Pagination } from '@/components/Pagination'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
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
import { PriorityBadge } from '@/features/projects/ProjectBadges'
import { useProjectContext } from '@/features/projects/projectContext'
import { usePermission } from '@/hooks/usePermissions'
import { formatDateTime } from '@/services/common'

const PAGE_SIZE = 25

export function ProjectIssuesPage() {
  const { project } = useProjectContext()
  const canWrite = usePermission('issues:write') && project.status !== 'archived'
  const [page, setPage] = useState(1)
  const issues = useIssues({ projectId: project.id, page, pageSize: PAGE_SIZE })

  return (
    <div className="space-y-4">
      {canWrite && (
        <div className="flex justify-end">
          <Button asChild>
            <Link to={`/projects/${project.id}/issues/new`}>Nova issue</Link>
          </Button>
        </div>
      )}
      {issues.isError && (
        <Alert variant="destructive">
          <AlertDescription>Não foi possível carregar as issues.</AlertDescription>
        </Alert>
      )}
      {issues.isPending && <p className="text-muted-foreground">A carregar…</p>}
      {issues.data && issues.data.items.length === 0 && (
        <p className="text-muted-foreground">Ainda não há issues neste projeto.</p>
      )}
      {issues.data && issues.data.items.length > 0 && (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Chave</TableHead>
                <TableHead>Título</TableHead>
                <TableHead>Tipo</TableHead>
                <TableHead>Estado</TableHead>
                <TableHead>Prioridade</TableHead>
                <TableHead>Responsável</TableHead>
                <TableHead>SP</TableHead>
                <TableHead>Atualizada</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {issues.data.items.map((issue) => (
                <TableRow key={issue.id}>
                  <TableCell className="font-mono">
                    <Link className="hover:underline" to={`/issues/${issue.key}`}>
                      {issue.key}
                    </Link>
                  </TableCell>
                  <TableCell>
                    <Link className="hover:underline" to={`/issues/${issue.key}`}>
                      {issue.title}
                    </Link>{' '}
                    {issue.blocked && <BlockedBadge />}
                  </TableCell>
                  <TableCell>
                    <IssueTypeBadge type={issue.type} />
                  </TableCell>
                  <TableCell>
                    <IssueStatusBadge status={issue.status} />
                  </TableCell>
                  <TableCell>
                    <PriorityBadge priority={issue.priority} />
                  </TableCell>
                  <TableCell>{issue.assignee?.name ?? '—'}</TableCell>
                  <TableCell>{issue.storyPoints ?? '—'}</TableCell>
                  <TableCell>{formatDateTime(issue.updatedAt)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Pagination
            page={issues.data.page}
            pageSize={issues.data.pageSize}
            total={issues.data.total}
            onChange={setPage}
          />
        </>
      )}
    </div>
  )
}
