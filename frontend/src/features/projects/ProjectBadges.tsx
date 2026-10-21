import { Badge } from '@/components/ui/badge'
import { priorityLabels, type Priority } from '@/services/common'
import { projectStatusLabels, type ProjectStatus } from '@/services/projects'

export function ProjectStatusBadge({ status }: { status: ProjectStatus }) {
  return (
    <Badge variant={status === 'archived' ? 'outline' : 'success'}>
      {projectStatusLabels[status]}
    </Badge>
  )
}

const priorityVariants = {
  low: 'outline',
  medium: 'outline',
  high: 'warning',
  critical: 'destructive',
} as const satisfies Record<Priority, string>

export function PriorityBadge({ priority }: { priority: Priority }) {
  return (
    <Badge variant={priorityVariants[priority]}>
      {priorityLabels[priority]}
    </Badge>
  )
}
