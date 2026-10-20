import { apiFetch } from '@/services/apiClient'
import type { UserSummary } from '@/services/common'

export type Attachment = {
  id: string
  issueId: string
  originalName: string
  contentType: string
  size: number
  sha256: string
  isImage: boolean
  uploadedBy: UserSummary | null
  createdAt: string
  canDelete: boolean
}

/** Igual a `ATTACHMENTS_MAX_BYTES` por omissão no backend (validação final é no servidor). */
export const ATTACHMENT_MAX_BYTES = 20 * 1024 * 1024

export const ATTACHMENT_EXTENSIONS = [
  'png',
  'jpg',
  'jpeg',
  'gif',
  'webp',
  'pdf',
  'txt',
  'log',
  'md',
  'csv',
  'json',
  'zip',
  'docx',
  'xlsx',
  'pptx',
]

export function listAttachments(issueId: string) {
  return apiFetch<Attachment[]>(`/issues/${issueId}/attachments`)
}

export function uploadAttachment(issueId: string, file: File) {
  const body = new FormData()
  body.append('file', file)
  return apiFetch<Attachment>(`/issues/${issueId}/attachments`, { method: 'POST', body })
}

export function deleteAttachment(attachmentId: string) {
  return apiFetch<void>(`/attachments/${attachmentId}`, { method: 'DELETE' })
}

export function attachmentUrl(attachmentId: string, inline = false) {
  return `/api/attachments/${attachmentId}/content${inline ? '?inline=1' : ''}`
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1).replace('.', ',')} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1).replace('.', ',')} MB`
}
