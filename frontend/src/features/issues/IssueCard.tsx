import type { DragEvent, ReactNode } from 'react'
import { Link } from 'react-router'

import { BlockedBadge, IssueTypeBadge } from '@/features/issues/IssueBadges'
import { PriorityBadge } from '@/features/projects/ProjectBadges'
import { cn } from '@/lib/utils'
import type { IssueSummary } from '@/services/issues'

type IssueCardProps = {
  issue: IssueSummary
  actions?: ReactNode
  draggable?: boolean
  onDragStart?: (event: DragEvent<HTMLElement>) => void
  onDragOver?: (event: DragEvent<HTMLElement>) => void
  onDrop?: (event: DragEvent<HTMLElement>) => void
  className?: string
}

/** Cartão de issue usado no backlog e no quadro. */
export function IssueCard({ issue, actions, className, ...dragProps }: IssueCardProps) {
  return (
    <article
      aria-label={`${issue.key} ${issue.title}`}
      data-issue-id={issue.id}
      className={cn(
        'space-y-2 rounded-lg border bg-card p-3 text-sm shadow-xs',
        dragProps.draggable && 'cursor-grab',
        issue.blocked && 'border-destructive',
        className,
      )}
      {...dragProps}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Link className="font-mono hover:underline" to={`/issues/${issue.key}`}>
          {issue.key}
        </Link>
        <IssueTypeBadge type={issue.type} />
        <PriorityBadge priority={issue.priority} />
        {issue.blocked && <BlockedBadge />}
      </div>
      <p className="font-medium">{issue.title}</p>
      <div className="flex flex-wrap items-center justify-between gap-2 text-muted-foreground">
        <span>
          {issue.assignee?.name ?? 'Sem responsável'}
          {issue.storyPoints !== null && ` · ${issue.storyPoints} SP`}
        </span>
        {actions}
      </div>
    </article>
  )
}
