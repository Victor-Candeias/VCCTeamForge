import { Badge } from '@/components/ui/badge'
import { priorityLabels, type Priority } from '@/services/common'
import { projectStatusLabels, type ProjectStatus } from '@/services/projects'

export function ProjectStatusBadge({ status }: { status: ProjectStatus }) {
  return (
    <Badge variant={status === 'archived' ? 'outline' : 'secondary'}>
      {projectStatusLabels[status]}
    </Badge>
  )
}

export function PriorityBadge({ priority }: { priority: Priority }) {
  return (
    <Badge variant={priority === 'critical' ? 'destructive' : 'outline'}>
      {priorityLabels[priority]}
    </Badge>
  )
}
