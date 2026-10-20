import { useState } from 'react'
import { Link } from 'react-router'

import { Pagination } from '@/components/Pagination'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
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
import { ReleaseStatusBadge } from '@/features/releases/ReleaseShared'
import { useReleases } from '@/features/releases/useReleases'
import { usePermission } from '@/hooks/usePermissions'
import { formatDate } from '@/services/common'
import { releaseStatusLabels, type ReleaseStatus } from '@/services/releases'

const PAGE_SIZE = 25

export function ReleasesPage() {
  const { project } = useProjectContext()
  const canManage = usePermission('releases:manage') && project.status !== 'archived'
  const [status, setStatus] = useState<ReleaseStatus | ''>('')
  const [q, setQ] = useState('')
  const [page, setPage] = useState(1)
  const releases = useReleases({
    projectId: project.id,
    status: status ? [status] : undefined,
    q: q.trim() || undefined,
    page,
    pageSize: PAGE_SIZE,
  })

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-wrap gap-4">
          <div className="space-y-1">
            <Label htmlFor="release-search">Versão</Label>
            <Input
              id="release-search"
              value={q}
              placeholder="Ex.: 1.4"
              onChange={(event) => {
                setQ(event.target.value)
                setPage(1)
              }}
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="release-status">Estado</Label>
            <NativeSelect
              id="release-status"
              value={status}
              onChange={(event) => {
                setStatus(event.target.value as ReleaseStatus | '')
                setPage(1)
              }}
            >
              <option value="">Todos</option>
              {Object.entries(releaseStatusLabels).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </NativeSelect>
          </div>
        </div>
        {canManage && (
          <Button asChild>
            <Link to={`/projects/${project.id}/releases/new`}>Nova release</Link>
          </Button>
        )}
      </div>

      {releases.isError && (
        <Alert variant="destructive">
          <AlertDescription>Não foi possível carregar as releases.</AlertDescription>
        </Alert>
      )}
      {releases.isPending && <p className="text-muted-foreground">A carregar…</p>}
      {releases.data && releases.data.items.length === 0 && (
        <p className="text-muted-foreground">Nenhuma release encontrada.</p>
      )}
      {releases.data && releases.data.items.length > 0 && (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Versão</TableHead>
                <TableHead>Estado</TableHead>
                <TableHead>Data prevista</TableHead>
                <TableHead>Publicada</TableHead>
                <TableHead>Issues</TableHead>
                <TableHead>Bugs conhecidos</TableHead>
                <TableHead>Checklist</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {releases.data.items.map((release) => (
                <TableRow key={release.id}>
                  <TableCell>
                    <Link
                      className="font-medium hover:underline"
                      to={`/projects/${project.id}/releases/${release.id}`}
                    >
                      {release.name}
                    </Link>
                  </TableCell>
                  <TableCell>
                    <ReleaseStatusBadge status={release.status} />
                  </TableCell>
                  <TableCell>{formatDate(release.plannedDate)}</TableCell>
                  <TableCell>{formatDate(release.releasedAt)}</TableCell>
                  <TableCell>{release.issueCount}</TableCell>
                  <TableCell>{release.knownBugCount}</TableCell>
                  <TableCell>
                    {release.checklistDone}/{release.checklistTotal}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Pagination
            page={releases.data.page}
            pageSize={releases.data.pageSize}
            total={releases.data.total}
            onChange={setPage}
          />
        </>
      )}
    </div>
  )
}
