import { useProjectContext } from '@/features/projects/projectContext'
import { formatDate, formatDateTime } from '@/services/common'

export function ProjectSummaryPage() {
  const { project } = useProjectContext()
  const rows: [string, string][] = [
    ['Responsável', project.lead?.name ?? '—'],
    ['Membros', String(project.memberCount)],
    ['Data de início', formatDate(project.startDate)],
    ['Data alvo', formatDate(project.targetDate)],
    ['Metodologia', project.settings.methodology],
    ['Duração do sprint', `${project.settings.sprintDurationDays} dias`],
    ['Estimativa', project.settings.estimationType],
    ['Atualizado em', formatDateTime(project.updatedAt)],
  ]
  return (
    <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
      <section className="space-y-2">
        <h2 className="font-medium">Descrição</h2>
        <p className="whitespace-pre-wrap text-sm">
          {project.description || <span className="text-muted-foreground">Sem descrição.</span>}
        </p>
      </section>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
        {rows.map(([label, value]) => (
          <div key={label} className="contents">
            <dt className="text-muted-foreground">{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}
