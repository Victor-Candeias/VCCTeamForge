import { useState } from 'react'
import { Link } from 'react-router'

import { Pagination } from '@/components/Pagination'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useProjectContext } from '@/features/projects/projectContext'
import { useSprints } from '@/features/sprints/useSprints'
import { usePermission } from '@/hooks/usePermissions'
import { formatDate } from '@/services/common'
import { sprintStatusLabels, type SprintStatus } from '@/services/sprints'

const PAGE_SIZE = 25

export function SprintStatusBadge({ status }: { status: SprintStatus }) {
  return (
    <Badge variant={status === 'active' ? 'default' : status === 'closed' ? 'outline' : 'secondary'}>
      {sprintStatusLabels[status]}
    </Badge>
  )
}

export function SprintsPage() {
  const { project } = useProjectContext()
  const canManage = usePermission('sprints:manage') && project.status !== 'archived'
  const [status, setStatus] = useState<SprintStatus | ''>('')
  const [page, setPage] = useState(1)
  const sprints = useSprints({
    projectId: project.id,
    status: status ? [status] : undefined,
    page,
    pageSize: PAGE_SIZE,
  })

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="space-y-1">
          <Label htmlFor="sprint-status">Estado</Label>
          <NativeSelect
            id="sprint-status"
            value={status}
            onChange={(event) => {
              setStatus(event.target.value as SprintStatus | '')
              setPage(1)
            }}
          >
            <option value="">Todos</option>
            {Object.entries(sprintStatusLabels).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </NativeSelect>
        </div>
        {canManage && (
          <Button asChild>
            <Link to={`/projects/${project.id}/sprints/new`}>Novo sprint</Link>
          </Button>
        )}
      </div>

      {sprints.isError && (
        <Alert variant="destructive">
          <AlertDescription>Não foi possível carregar os sprints.</AlertDescription>
        </Alert>
      )}
      {sprints.isPending && <p className="text-muted-foreground">A carregar…</p>}
      {sprints.data && sprints.data.items.length === 0 && (
        <p className="text-muted-foreground">Nenhum sprint encontrado.</p>
      )}
      {sprints.data && sprints.data.items.length > 0 && (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Nome</TableHead>
                <TableHead>Estado</TableHead>
                <TableHead>Início</TableHead>
                <TableHead>Fim</TableHead>
                <TableHead>Dias</TableHead>
                <TableHead>Issues</TableHead>
                <TableHead>SP</TableHead>
                <TableHead>Objetivo</TableHead>
                {canManage && <TableHead className="w-24" />}
              </TableRow>
            </TableHeader>
            <TableBody>
              {sprints.data.items.map((sprint) => (
                <TableRow key={sprint.id}>
                  <TableCell className="font-medium">
                    <Link
                      className="hover:underline"
                      to={`/projects/${project.id}/sprints/${sprint.id}`}
                    >
                      {sprint.name}
                    </Link>
                  </TableCell>
                  <TableCell>
                    <SprintStatusBadge status={sprint.status} />
                  </TableCell>
                  <TableCell>{formatDate(sprint.startDate)}</TableCell>
                  <TableCell>{formatDate(sprint.endDate)}</TableCell>
                  <TableCell>{sprint.durationDays}</TableCell>
                  <TableCell>{sprint.scope.issueCount}</TableCell>
                  <TableCell>
                    {sprint.scope.storyPoints}
                    {sprint.capacityStoryPoints !== null && ` / ${sprint.capacityStoryPoints}`}
                  </TableCell>
                  <TableCell className="max-w-md truncate" title={sprint.goal}>
                    {sprint.goal || '—'}
                  </TableCell>
                  {canManage && (
                    <TableCell>
                      {sprint.canEdit && (
                        <Button variant="ghost" size="sm" asChild>
                          <Link
                            to={`/projects/${project.id}/sprints/${sprint.id}/edit`}
                            aria-label={`Editar ${sprint.name}`}
                          >
                            Editar
                          </Link>
                        </Button>
                      )}
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Pagination
            page={sprints.data.page}
            pageSize={sprints.data.pageSize}
            total={sprints.data.total}
            onChange={setPage}
          />
        </>
      )}
    </div>
  )
}
