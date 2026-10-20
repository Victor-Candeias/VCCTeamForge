import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createIssue,
  getIssueByKey,
  listIssues,
  updateIssue,
  type Issue,
  type IssueFilters,
  type IssueUpdateInput,
} from '@/services/issues'

export const issueKeys = {
  all: ['issues'] as const,
  list: (filters: IssueFilters) => ['issues', 'list', filters] as const,
  detail: (key: string) => ['issues', 'detail', key] as const,
}

export function useIssues(filters: IssueFilters, enabled = true) {
  return useQuery({
    queryKey: issueKeys.list(filters),
    queryFn: () => listIssues(filters),
    placeholderData: keepPreviousData,
    enabled,
  })
}

export function useIssue(key: string) {
  return useQuery({ queryKey: issueKeys.detail(key), queryFn: () => getIssueByKey(key) })
}

export function useIssueCacheUpdate() {
  const queryClient = useQueryClient()
  return (issue: Issue) => {
    queryClient.setQueryData(issueKeys.detail(issue.key), issue)
    void queryClient.invalidateQueries({ queryKey: ['issues', 'list'] })
  }
}

export function useCreateIssue() {
  const update = useIssueCacheUpdate()
  return useMutation({ mutationFn: createIssue, onSuccess: update })
}

export function useUpdateIssue(issueId: string) {
  const update = useIssueCacheUpdate()
  return useMutation({
    mutationFn: (input: IssueUpdateInput) => updateIssue(issueId, input),
    onSuccess: update,
  })
}
