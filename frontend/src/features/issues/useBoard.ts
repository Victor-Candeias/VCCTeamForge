import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { mutationErrorMessage } from '@/lib/errors'
import { ApiError } from '@/services/apiClient'
import {
  getBoard,
  moveIssueRank,
  updateIssue,
  type BoardParams,
  type IssueStatus,
  type RankMoveInput,
} from '@/services/issues'

export const boardKeys = {
  board: (projectId: string, params: BoardParams) =>
    ['issues', 'board', projectId, params] as const,
}

export function useBoard(projectId: string, params: BoardParams) {
  return useQuery({
    queryKey: boardKeys.board(projectId, params),
    queryFn: () => getBoard(projectId, params),
  })
}

/** Recarrega listas e quadro depois de uma alteração (com sucesso ou não). */
function useRefreshIssues() {
  const queryClient = useQueryClient()
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: ['issues', 'list'] }),
      queryClient.invalidateQueries({ queryKey: ['issues', 'board'] }),
    ])
}

export function useMoveIssueRank() {
  const refresh = useRefreshIssues()
  return useMutation({
    mutationFn: ({ issueId, ...input }: RankMoveInput & { issueId: string }) =>
      moveIssueRank(issueId, input),
    onSettled: refresh,
  })
}

type StatusMoveInput = { issueId: string; status: IssueStatus; version: number }

export function useMoveIssueStatus() {
  const queryClient = useQueryClient()
  const refresh = useRefreshIssues()
  return useMutation({
    mutationFn: ({ issueId, ...input }: StatusMoveInput) => updateIssue(issueId, input),
    onSuccess: (issue) =>
      queryClient.invalidateQueries({
        queryKey: ['issues', 'history', issue.id],
      }),
    onSettled: refresh,
  })
}

/** As vistas recarregam sozinhas após um erro, por isso o 409 não pede para recarregar. */
export function moveErrorMessage(error: unknown) {
  if (error instanceof ApiError && error.isConflict) {
    return 'A issue foi alterada por outra pessoa; a vista foi atualizada.'
  }
  return mutationErrorMessage(error)
}
