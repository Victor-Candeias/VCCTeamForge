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
import { PriorityBadge, ProjectStatusBadge } from '@/features/projects/ProjectBadges'
import { useProjects } from '@/features/projects/useProjects'
import { usePermission } from '@/hooks/usePermissions'
import { formatDate } from '@/services/common'
import { projectStatusLabels, type ProjectStatus } from '@/services/projects'

const PAGE_SIZE = 25

export function ProjectsPage() {
  const canManage = usePermission('projects:manage')
  const [q, setQ] = useState('')
  const [status, setStatus] = useState<ProjectStatus | ''>('')
  const [includeArchived, setIncludeArchived] = useState(false)
  const [page, setPage] = useState(1)
  const projects = useProjects({
    q: q.trim() || undefined,
    status: status ? [status] : undefined,
    includeArchived: includeArchived || status === 'archived',
    page,
    pageSize: PAGE_SIZE,
  })

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-semibold">Projetos</h1>
        {canManage && (
          <Button asChild>
            <Link to="/projects/new">Novo projeto</Link>
          </Button>
        )}
      </div>

      <div className="flex flex-wrap items-end gap-4">
        <div className="space-y-1">
          <Label htmlFor="project-search">Pesquisar</Label>
          <Input
            id="project-search"
            placeholder="Nome ou chave"
            value={q}
            onChange={(event) => {
              setQ(event.target.value)
              setPage(1)
            }}
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="project-status">Estado</Label>
          <NativeSelect
            id="project-status"
            value={status}
            onChange={(event) => {
              setStatus(event.target.value as ProjectStatus | '')
              setPage(1)
            }}
          >
            <option value="">Todos</option>
            {Object.entries(projectStatusLabels).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </NativeSelect>
        </div>
        <label className="flex items-center gap-2 pb-1.5 text-sm">
          <input
            type="checkbox"
            checked={includeArchived}
            onChange={(event) => {
              setIncludeArchived(event.target.checked)
              setPage(1)
            }}
          />
          Incluir arquivados
        </label>
      </div>

      {projects.isError && (
        <Alert variant="destructive">
          <AlertDescription>Não foi possível carregar os projetos.</AlertDescription>
        </Alert>
      )}
      {projects.isPending && <p className="text-muted-foreground">A carregar…</p>}
      {projects.data && projects.data.items.length === 0 && (
        <p className="text-muted-foreground">Nenhum projeto encontrado.</p>
      )}
      {projects.data && projects.data.items.length > 0 && (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Chave</TableHead>
                <TableHead>Nome</TableHead>
                <TableHead>Estado</TableHead>
                <TableHead>Prioridade</TableHead>
                <TableHead>Responsável</TableHead>
                <TableHead>Início</TableHead>
                <TableHead>Data alvo</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {projects.data.items.map((project) => (
                <TableRow key={project.id}>
                  <TableCell className="font-mono">{project.key}</TableCell>
                  <TableCell>
                    <Link className="font-medium hover:underline" to={`/projects/${project.id}`}>
                      {project.name}
                    </Link>
                  </TableCell>
                  <TableCell>
                    <ProjectStatusBadge status={project.status} />
                  </TableCell>
                  <TableCell>
                    <PriorityBadge priority={project.priority} />
                  </TableCell>
                  <TableCell>{project.lead?.name ?? '—'}</TableCell>
                  <TableCell>{formatDate(project.startDate)}</TableCell>
                  <TableCell>{formatDate(project.targetDate)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Pagination
            page={projects.data.page}
            pageSize={projects.data.pageSize}
            total={projects.data.total}
            onChange={setPage}
          />
        </>
      )}
    </div>
  )
}
