import { useState } from 'react'

import { Markdown } from '@/components/Markdown'
import { Pagination } from '@/components/Pagination'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  useComments,
  useCreateComment,
  useDeleteComment,
  useUpdateComment,
} from '@/features/issues/useComments'
import { usePermission } from '@/hooks/usePermissions'
import { mutationErrorMessage } from '@/lib/errors'
import type { Comment } from '@/services/comments'
import { formatDateTime } from '@/services/common'

const COMMENT_MAX_LENGTH = 10000

function CommentItem({ issueId, comment }: { issueId: string; comment: Comment }) {
  const update = useUpdateComment(issueId)
  const remove = useDeleteComment(issueId)
  const [editing, setEditing] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [text, setText] = useState(comment.body ?? '')
  const error = update.error ?? remove.error

  return (
    <li className="space-y-2 rounded-lg border p-3" aria-label={`Comentário de ${comment.author?.name ?? 'utilizador removido'}`}>
      <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
        <span className="font-medium text-foreground">
          {comment.author?.name ?? 'Utilizador removido'}
        </span>
        <span>{formatDateTime(comment.createdAt)}</span>
        {comment.editedAt && !comment.deleted && <span>(editado)</span>}
      </div>
      {comment.deleted ? (
        <p className="text-sm text-muted-foreground italic">Comentário removido</p>
      ) : editing ? (
        <form
          className="space-y-2"
          onSubmit={(event) => {
            event.preventDefault()
            if (!text.trim()) return
            update.mutate(
              { commentId: comment.id, body: text.trim() },
              { onSuccess: () => setEditing(false) },
            )
          }}
        >
          <Label htmlFor={`edit-${comment.id}`} className="sr-only">
            Editar comentário
          </Label>
          <Textarea
            id={`edit-${comment.id}`}
            rows={4}
            maxLength={COMMENT_MAX_LENGTH}
            value={text}
            onChange={(event) => setText(event.target.value)}
          />
          <div className="flex gap-2">
            <Button type="submit" size="sm" disabled={!text.trim() || update.isPending}>
              Guardar
            </Button>
            <Button type="button" size="sm" variant="ghost" onClick={() => setEditing(false)}>
              Cancelar
            </Button>
          </div>
        </form>
      ) : (
        <Markdown>{comment.body ?? ''}</Markdown>
      )}
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{mutationErrorMessage(error)}</AlertDescription>
        </Alert>
      )}
      {!comment.deleted && !editing && (comment.canEdit || comment.canDelete) && (
        <div className="flex gap-2">
          {comment.canEdit && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setText(comment.body ?? '')
                setEditing(true)
              }}
            >
              Editar
            </Button>
          )}
          {comment.canDelete &&
            (confirming ? (
              <>
                <Button
                  size="sm"
                  variant="destructive"
                  disabled={remove.isPending}
                  onClick={() => remove.mutate(comment.id)}
                >
                  Confirmar remoção
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setConfirming(false)}>
                  Cancelar
                </Button>
              </>
            ) : (
              <Button size="sm" variant="ghost" onClick={() => setConfirming(true)}>
                Remover
              </Button>
            ))}
        </div>
      )}
    </li>
  )
}

function NewComment({ issueId }: { issueId: string }) {
  const create = useCreateComment(issueId)
  const [text, setText] = useState('')
  return (
    <form
      className="space-y-2"
      onSubmit={(event) => {
        event.preventDefault()
        if (!text.trim()) return
        create.mutate(text.trim(), { onSuccess: () => setText('') })
      }}
    >
      <Label htmlFor="new-comment">Novo comentário (Markdown)</Label>
      <Textarea
        id="new-comment"
        rows={3}
        maxLength={COMMENT_MAX_LENGTH}
        value={text}
        onChange={(event) => setText(event.target.value)}
      />
      {create.isError && (
        <Alert variant="destructive">
          <AlertDescription>{mutationErrorMessage(create.error)}</AlertDescription>
        </Alert>
      )}
      <Button type="submit" size="sm" disabled={!text.trim() || create.isPending}>
        Comentar
      </Button>
    </form>
  )
}

export function IssueComments({ issueId }: { issueId: string }) {
  const canComment = usePermission('issues:comment')
  const [page, setPage] = useState(1)
  const comments = useComments(issueId, page)

  return (
    <div className="space-y-4">
      {comments.isPending && <p className="text-muted-foreground">A carregar…</p>}
      {comments.isError && (
        <Alert variant="destructive">
          <AlertDescription>Não foi possível carregar os comentários.</AlertDescription>
        </Alert>
      )}
      {comments.data && comments.data.items.length === 0 && (
        <p className="text-sm text-muted-foreground">Ainda não há comentários.</p>
      )}
      {comments.data && comments.data.items.length > 0 && (
        <>
          <ul className="space-y-3">
            {comments.data.items.map((comment) => (
              <CommentItem
                key={`${comment.id}-${comment.editedAt ?? ''}`}
                issueId={issueId}
                comment={comment}
              />
            ))}
          </ul>
          {comments.data.total > comments.data.pageSize && (
            <Pagination
              page={comments.data.page}
              pageSize={comments.data.pageSize}
              total={comments.data.total}
              onChange={setPage}
            />
          )}
        </>
      )}
      {canComment && <NewComment issueId={issueId} />}
    </div>
  )
}
