import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createIssue,
  getIssueByKey,
  listProjectLabels,
  searchIssues,
  updateIssue,
  type Issue,
  type IssueSearchParams,
  type IssueUpdateInput,
} from '@/services/issues'

export const issueKeys = {
  all: ['issues'] as const,
  list: (params: IssueSearchParams) => ['issues', 'list', params] as const,
  labels: (projectId: string) => ['issues', 'labels', projectId] as const,
  detail: (key: string) => ['issues', 'detail', key] as const,
}

export function useIssues(params: IssueSearchParams, enabled = true) {
  return useQuery({
    queryKey: issueKeys.list(params),
    queryFn: () => searchIssues(params),
    placeholderData: keepPreviousData,
    enabled,
  })
}

export function useProjectLabels(projectId: string) {
  return useQuery({
    queryKey: issueKeys.labels(projectId),
    queryFn: () => listProjectLabels(projectId),
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
    void queryClient.invalidateQueries({ queryKey: ['issues', 'labels'] })
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
