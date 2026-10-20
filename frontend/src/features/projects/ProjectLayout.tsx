import { Link, NavLink, Outlet, useParams } from 'react-router'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { PriorityBadge, ProjectStatusBadge } from '@/features/projects/ProjectBadges'
import { projectTabs } from '@/features/projects/projectContext'
import { useArchiveProject, useProject } from '@/features/projects/useProjects'
import { mutationErrorMessage } from '@/lib/errors'
import { cn } from '@/lib/utils'

export function ProjectLayout() {
  const { projectId = '' } = useParams()
  const project = useProject(projectId)
  const archive = useArchiveProject(projectId)

  if (project.isPending) return <p className="text-muted-foreground">A carregar…</p>
  if (project.isError) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Projeto não encontrado ou sem acesso.</AlertDescription>
      </Alert>
    )
  }

  const data = project.data
  const archived = data.status === 'archived'

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1">
          <p className="font-mono text-sm text-muted-foreground">{data.key}</p>
          <h1 className="text-2xl font-semibold">{data.name}</h1>
          <div className="flex gap-2">
            <ProjectStatusBadge status={data.status} />
            <PriorityBadge priority={data.priority} />
          </div>
        </div>
        {data.canManage && (
          <div className="flex gap-2">
            {!archived && (
              <Button variant="outline" asChild>
                <Link to={`/projects/${data.id}/edit`}>Editar</Link>
              </Button>
            )}
            <Button
              variant={archived ? 'outline' : 'destructive'}
              disabled={archive.isPending}
              onClick={() => {
                const message = archived
                  ? `Restaurar o projeto ${data.key}?`
                  : `Arquivar o projeto ${data.key}? Fica só de leitura.`
                if (window.confirm(message)) {
                  archive.mutate({ archive: !archived, version: data.version })
                }
              }}
            >
              {archived ? 'Restaurar' : 'Arquivar'}
            </Button>
          </div>
        )}
      </div>
      {archive.isError && (
        <Alert variant="destructive">
          <AlertDescription>{mutationErrorMessage(archive.error)}</AlertDescription>
        </Alert>
      )}
      {archived && (
        <Alert>
          <AlertDescription>Projeto arquivado: apenas leitura.</AlertDescription>
        </Alert>
      )}
      <nav className="flex flex-wrap gap-1 border-b text-sm" aria-label="Secções do projeto">
        {projectTabs.map((tab) =>
          tab.disabled ? (
            <span
              key={tab.label}
              aria-disabled="true"
              title="Disponível em breve"
              className="cursor-not-allowed px-3 py-2 text-muted-foreground/60"
            >
              {tab.label}
            </span>
          ) : (
            <NavLink
              key={tab.label}
              to={tab.to}
              end={tab.end}
              className={({ isActive }) =>
                cn(
                  '-mb-px border-b-2 border-transparent px-3 py-2 text-muted-foreground hover:text-foreground',
                  isActive && 'border-primary text-foreground',
                )
              }
            >
              {tab.label}
            </NavLink>
          ),
        )}
      </nav>
      <Outlet context={{ project: data }} />
    </div>
  )
}
