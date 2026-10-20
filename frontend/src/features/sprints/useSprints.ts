import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  addSprintIssues,
  createSprint,
  getSprint,
  getSprintCommitment,
  listSprints,
  removeSprintIssue,
  startSprint,
  updateSprint,
  type Sprint,
  type SprintFilters,
} from '@/services/sprints'

export const sprintKeys = {
  all: ['sprints'] as const,
  list: (filters: SprintFilters) => ['sprints', 'list', filters] as const,
  detail: (sprintId: string) => ['sprints', 'detail', sprintId] as const,
  commitment: (sprintId: string) => ['sprints', 'commitment', sprintId] as const,
}

export function useSprints(filters: SprintFilters) {
  return useQuery({
    queryKey: sprintKeys.list(filters),
    queryFn: () => listSprints(filters),
    placeholderData: keepPreviousData,
  })
}

export function useSprint(sprintId: string) {
  return useQuery({
    queryKey: sprintKeys.detail(sprintId),
    queryFn: () => getSprint(sprintId),
    enabled: Boolean(sprintId),
  })
}

function useSprintCacheUpdate() {
  const queryClient = useQueryClient()
  return (sprint: Sprint) => {
    queryClient.setQueryData(sprintKeys.detail(sprint.id), sprint)
    void queryClient.invalidateQueries({ queryKey: ['sprints', 'list'] })
  }
}

export function useCreateSprint() {
  const update = useSprintCacheUpdate()
  return useMutation({ mutationFn: createSprint, onSuccess: update })
}

export function useUpdateSprint(sprintId: string) {
  const update = useSprintCacheUpdate()
  return useMutation({
    mutationFn: (input: Parameters<typeof updateSprint>[1]) => updateSprint(sprintId, input),
    onSuccess: update,
  })
}

/** Associar/remover issues muda o sprint e as listas de issues (backlog, quadro). */
function useSprintScopeUpdate() {
  const queryClient = useQueryClient()
  const update = useSprintCacheUpdate()
  return (sprint: Sprint) => {
    update(sprint)
    void queryClient.invalidateQueries({ queryKey: ['issues'] })
    void queryClient.invalidateQueries({ queryKey: ['sprints', 'commitment', sprint.id] })
  }
}

export function useAddSprintIssues(sprintId: string) {
  const update = useSprintScopeUpdate()
  return useMutation({
    mutationFn: (issueIds: string[]) => addSprintIssues(sprintId, issueIds),
    onSuccess: update,
  })
}

export function useRemoveSprintIssue(sprintId: string) {
  const update = useSprintScopeUpdate()
  return useMutation({
    mutationFn: (issueId: string) => removeSprintIssue(sprintId, issueId),
    onSuccess: update,
  })
}

export function useSprintCommitment(sprintId: string, enabled: boolean) {
  return useQuery({
    queryKey: sprintKeys.commitment(sprintId),
    queryFn: () => getSprintCommitment(sprintId),
    enabled,
  })
}

/** Iniciar muda o estado do sprint e cria o compromisso. */
export function useStartSprint(sprintId: string) {
  const queryClient = useQueryClient()
  const update = useSprintCacheUpdate()
  return useMutation({
    mutationFn: (version: number) => startSprint(sprintId, version),
    onSuccess: (sprint) => {
      update(sprint)
      void queryClient.invalidateQueries({ queryKey: sprintKeys.commitment(sprintId) })
      void queryClient.invalidateQueries({ queryKey: ['issues', 'board'] })
    },
  })
}
