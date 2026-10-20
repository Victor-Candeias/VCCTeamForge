import { Link } from 'react-router'

import { Pagination } from '@/components/Pagination'
import { SortableHeader } from '@/components/SortableHeader'
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
import { IssueFilters } from '@/features/issues/IssueFilters'
import { useIssueSearchParams } from '@/features/issues/useIssueSearchParams'
import { useIssues } from '@/features/issues/useIssues'
import { PriorityBadge } from '@/features/projects/ProjectBadges'
import { useProjectContext } from '@/features/projects/projectContext'
import { usePermission } from '@/hooks/usePermissions'
import { formatDateTime } from '@/services/common'

export function ProjectIssuesPage() {
  const { project } = useProjectContext()
  const canWrite = usePermission('issues:write') && project.status !== 'archived'
  const search = useIssueSearchParams(project.id)
  const issues = useIssues(search.params)
  const sortable = (field: string, label: string) => (
    <SortableHeader field={field} label={label} sort={search.sort} onSort={search.setSort} />
  )

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <IssueFilters
          projectId={project.id}
          filters={search.filters}
          activeFilters={search.activeFilters}
          onChange={search.setFilter}
          onClear={search.clearFilters}
        />
        {canWrite && (
          <Button asChild>
            <Link to={`/projects/${project.id}/issues/new`}>Nova issue</Link>
          </Button>
        )}
      </div>
      {issues.isError && (
        <Alert variant="destructive">
          <AlertDescription>Não foi possível carregar as issues.</AlertDescription>
        </Alert>
      )}
      {issues.isPending && <p className="text-muted-foreground">A carregar…</p>}
      {issues.data && issues.data.items.length === 0 && (
        <p className="text-muted-foreground">
          {search.activeFilters > 0
            ? 'Nenhuma issue corresponde aos filtros.'
            : 'Ainda não há issues neste projeto.'}
        </p>
      )}
      {issues.data && issues.data.items.length > 0 && (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                {sortable('number', 'Chave')}
                {sortable('title', 'Título')}
                <TableHead>Tipo</TableHead>
                {sortable('status', 'Estado')}
                {sortable('priority', 'Prioridade')}
                <TableHead>Responsável</TableHead>
                <TableHead>SP</TableHead>
                {sortable('updatedAt', 'Atualizada')}
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
            onChange={search.setPage}
            onPageSizeChange={search.setPageSize}
          />
        </>
      )}
    </div>
  )
}
