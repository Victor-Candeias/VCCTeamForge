import { Badge } from '@/components/ui/badge'
import { releaseStatusLabels, type ReleaseStatus } from '@/services/releases'

const variants: Record<ReleaseStatus, 'secondary' | 'info' | 'warning' | 'success'> = {
  draft: 'secondary',
  ready_for_qa: 'warning',
  approved: 'info',
  released: 'success',
}

export function ReleaseStatusBadge({ status }: { status: ReleaseStatus }) {
  return <Badge variant={variants[status]}>{releaseStatusLabels[status]}</Badge>
}
