import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createComment,
  deleteComment,
  listComments,
  listHistory,
  updateComment,
} from '@/services/comments'

export const COMMENTS_PAGE_SIZE = 50
export const HISTORY_PAGE_SIZE = 25

export const activityKeys = {
  comments: (issueId: string, page: number) => ['issues', 'comments', issueId, page] as const,
  history: (issueId: string, page: number) => ['issues', 'history', issueId, page] as const,
}

export function useComments(issueId: string, page: number) {
  return useQuery({
    queryKey: activityKeys.comments(issueId, page),
    queryFn: () => listComments(issueId, { page, pageSize: COMMENTS_PAGE_SIZE }),
    placeholderData: keepPreviousData,
  })
}

export function useHistory(issueId: string, page: number) {
  return useQuery({
    queryKey: activityKeys.history(issueId, page),
    queryFn: () => listHistory(issueId, { page, pageSize: HISTORY_PAGE_SIZE }),
    placeholderData: keepPreviousData,
  })
}

function useActivityInvalidation(issueId: string) {
  const queryClient = useQueryClient()
  return () => {
    void queryClient.invalidateQueries({ queryKey: ['issues', 'comments', issueId] })
    void queryClient.invalidateQueries({ queryKey: ['issues', 'history', issueId] })
  }
}

export function useCreateComment(issueId: string) {
  const onSuccess = useActivityInvalidation(issueId)
  return useMutation({ mutationFn: (body: string) => createComment(issueId, body), onSuccess })
}

export function useUpdateComment(issueId: string) {
  const onSuccess = useActivityInvalidation(issueId)
  return useMutation({
    mutationFn: ({ commentId, body }: { commentId: string; body: string }) =>
      updateComment(issueId, commentId, body),
    onSuccess,
  })
}

export function useDeleteComment(issueId: string) {
  const onSuccess = useActivityInvalidation(issueId)
  return useMutation({
    mutationFn: (commentId: string) => deleteComment(issueId, commentId),
    onSuccess,
  })
}
