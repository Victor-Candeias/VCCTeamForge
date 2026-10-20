import { apiFetch, toQueryString } from '@/services/apiClient'
import type { Page, UserSummary } from '@/services/common'

export type Comment = {
  id: string
  issueId: string
  author: UserSummary | null
  body: string | null
  deleted: boolean
  createdAt: string
  editedAt: string | null
  deletedAt: string | null
  canEdit: boolean
  canDelete: boolean
}

export type FieldChange = { field: string; from: unknown; to: unknown }

export type HistoryEventType =
  | 'created'
  | 'updated'
  | 'comment_added'
  | 'comment_edited'
  | 'comment_deleted'
  | 'attachment_added'
  | 'attachment_removed'

export type HistoryEvent = {
  id: string
  type: HistoryEventType
  actor: UserSummary | null
  changes: FieldChange[]
  details: Record<string, unknown>
  createdAt: string
}

type PageQuery = { page?: number; pageSize?: number }

export function listComments(issueId: string, query: PageQuery = {}) {
  return apiFetch<Page<Comment>>(`/issues/${issueId}/comments${toQueryString(query)}`)
}

export function createComment(issueId: string, body: string) {
  return apiFetch<Comment>(`/issues/${issueId}/comments`, {
    method: 'POST',
    body: JSON.stringify({ body }),
  })
}

export function updateComment(issueId: string, commentId: string, body: string) {
  return apiFetch<Comment>(`/issues/${issueId}/comments/${commentId}`, {
    method: 'PATCH',
    body: JSON.stringify({ body }),
  })
}

export function deleteComment(issueId: string, commentId: string) {
  return apiFetch<void>(`/issues/${issueId}/comments/${commentId}`, { method: 'DELETE' })
}

export function listHistory(issueId: string, query: PageQuery = {}) {
  return apiFetch<Page<HistoryEvent>>(`/issues/${issueId}/history${toQueryString(query)}`)
}
