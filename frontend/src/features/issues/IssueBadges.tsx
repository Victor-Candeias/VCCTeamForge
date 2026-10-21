import { Badge } from '@/components/ui/badge'
import {
  issueStatusLabels,
  issueTypeLabels,
  type IssueStatus,
  type IssueType,
} from '@/services/issues'

const statusVariants = {
  todo: 'secondary',
  in_progress: 'info',
  code_review: 'info',
  testing: 'warning',
  done: 'success',
} as const satisfies Record<IssueStatus, string>

export function IssueStatusBadge({ status }: { status: IssueStatus }) {
  return <Badge variant={statusVariants[status]}>{issueStatusLabels[status]}</Badge>
}

export function IssueTypeBadge({ type }: { type: IssueType }) {
  return (
    <Badge variant={type === 'bug' ? 'destructive' : 'outline'}>{issueTypeLabels[type]}</Badge>
  )
}

export function BlockedBadge() {
  return <Badge variant="destructive">Bloqueada</Badge>
}
