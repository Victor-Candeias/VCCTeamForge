import { Badge } from '@/components/ui/badge'
import { releaseStatusLabels, type ReleaseStatus } from '@/services/releases'

const variants: Record<ReleaseStatus, 'default' | 'secondary' | 'outline'> = {
  draft: 'secondary',
  ready_for_qa: 'outline',
  approved: 'default',
  released: 'default',
}

export function ReleaseStatusBadge({ status }: { status: ReleaseStatus }) {
  return <Badge variant={variants[status]}>{releaseStatusLabels[status]}</Badge>
}
