import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { usePermission } from '@/hooks/usePermissions'
import { mutationErrorMessage } from '@/lib/errors'
import {
  ATTACHMENT_EXTENSIONS,
  ATTACHMENT_MAX_BYTES,
  attachmentUrl,
  deleteAttachment,
  formatFileSize,
  listAttachments,
  uploadAttachment,
  type Attachment,
} from '@/services/attachments'
import { formatDateTime } from '@/services/common'

const accept = ATTACHMENT_EXTENSIONS.map((extension) => `.${extension}`).join(',')

function useAttachmentMutations(issueId: string) {
  const queryClient = useQueryClient()
  const onSuccess = () => {
    void queryClient.invalidateQueries({ queryKey: ['issues', 'attachments', issueId] })
    void queryClient.invalidateQueries({ queryKey: ['issues', 'history', issueId] })
  }
  return {
    upload: useMutation({
      mutationFn: (file: File) => uploadAttachment(issueId, file),
      onSuccess,
    }),
    remove: useMutation({ mutationFn: deleteAttachment, onSuccess }),
  }
}

function AttachmentRow({
  attachment,
  onRemove,
  removing,
}: {
  attachment: Attachment
  onRemove: () => void
  removing: boolean
}) {
  const [confirming, setConfirming] = useState(false)
  return (
    <li className="flex flex-wrap items-center gap-3 rounded-lg border p-2 text-sm">
      {attachment.isImage && (
        <img
          src={attachmentUrl(attachment.id, true)}
          alt=""
          className="size-10 rounded object-cover"
          loading="lazy"
        />
      )}
      <div className="min-w-0 flex-1">
        <a className="font-medium hover:underline" href={attachmentUrl(attachment.id)} download>
          {attachment.originalName}
        </a>
        <div className="text-muted-foreground">
          {formatFileSize(attachment.size)} · {attachment.uploadedBy?.name ?? 'Utilizador removido'}{' '}
          · {formatDateTime(attachment.createdAt)}
        </div>
      </div>
      {attachment.canDelete &&
        (confirming ? (
          <div className="flex gap-2">
            <Button size="sm" variant="destructive" disabled={removing} onClick={onRemove}>
              Confirmar remoção
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setConfirming(false)}>
              Cancelar
            </Button>
          </div>
        ) : (
          <Button
            size="sm"
            variant="ghost"
            aria-label={`Remover ${attachment.originalName}`}
            onClick={() => setConfirming(true)}
          >
            Remover
          </Button>
        ))}
    </li>
  )
}

export function IssueAttachments({ issueId }: { issueId: string }) {
  const canUpload = usePermission('issues:write')
  const attachments = useQuery({
    queryKey: ['issues', 'attachments', issueId],
    queryFn: () => listAttachments(issueId),
  })
  const { upload, remove } = useAttachmentMutations(issueId)
  const [clientError, setClientError] = useState<string | null>(null)
  const input = useRef<HTMLInputElement>(null)
  const mutationError = upload.error ?? remove.error
  const error = clientError ?? (mutationError ? mutationErrorMessage(mutationError) : null)

  const onFile = (file: File | undefined) => {
    upload.reset()
    remove.reset()
    setClientError(null)
    if (!file) return
    if (file.size > ATTACHMENT_MAX_BYTES) {
      setClientError(`O ficheiro excede o máximo de ${formatFileSize(ATTACHMENT_MAX_BYTES)}.`)
    } else {
      upload.mutate(file)
    }
    if (input.current) input.current.value = ''
  }

  return (
    <section className="space-y-2">
      <h2 className="font-medium">Anexos</h2>
      {attachments.isError && (
        <Alert variant="destructive">
          <AlertDescription>Não foi possível carregar os anexos.</AlertDescription>
        </Alert>
      )}
      {attachments.data && attachments.data.length === 0 && (
        <p className="text-sm text-muted-foreground">Sem anexos.</p>
      )}
      {attachments.data && attachments.data.length > 0 && (
        <ul className="space-y-2">
          {attachments.data.map((attachment) => (
            <AttachmentRow
              key={attachment.id}
              attachment={attachment}
              removing={remove.isPending}
              onRemove={() => remove.mutate(attachment.id)}
            />
          ))}
        </ul>
      )}
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {canUpload && (
        <div className="space-y-1">
          <Label htmlFor="attachment-file">Adicionar anexo</Label>
          <input
            ref={input}
            id="attachment-file"
            type="file"
            accept={accept}
            disabled={upload.isPending}
            className="block text-sm file:mr-3 file:rounded-md file:border file:bg-background file:px-3 file:py-1"
            onChange={(event) => onFile(event.target.files?.[0])}
          />
          <p className="text-xs text-muted-foreground">
            {upload.isPending
              ? 'A carregar…'
              : `Máximo ${formatFileSize(ATTACHMENT_MAX_BYTES)}; tipos: ${ATTACHMENT_EXTENSIONS.join(', ')}.`}
          </p>
        </div>
      )}
    </section>
  )
}
