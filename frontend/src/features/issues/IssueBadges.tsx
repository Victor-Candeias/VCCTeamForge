import { Badge } from '@/components/ui/badge'
import {
  issueStatusLabels,
  issueTypeLabels,
  type IssueStatus,
  type IssueType,
} from '@/services/issues'

export function IssueStatusBadge({ status }: { status: IssueStatus }) {
  return (
    <Badge variant={status === 'done' ? 'default' : 'secondary'}>{issueStatusLabels[status]}</Badge>
  )
}

export function IssueTypeBadge({ type }: { type: IssueType }) {
  return (
    <Badge variant={type === 'bug' ? 'destructive' : 'outline'}>{issueTypeLabels[type]}</Badge>
  )
}

export function BlockedBadge() {
  return <Badge variant="destructive">Bloqueada</Badge>
}
