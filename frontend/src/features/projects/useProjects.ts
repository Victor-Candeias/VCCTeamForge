import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  addMember,
  archiveProject,
  createProject,
  getProject,
  listMembers,
  listProjects,
  removeMember,
  restoreProject,
  searchUsers,
  updateProject,
  type Project,
  type ProjectFilters,
  type ProjectMembers,
} from '@/services/projects'

export const projectKeys = {
  all: ['projects'] as const,
  list: (filters: ProjectFilters) => ['projects', 'list', filters] as const,
  detail: (projectId: string) => ['projects', 'detail', projectId] as const,
  members: (projectId: string) => ['projects', 'detail', projectId, 'members'] as const,
}

export function useProjects(filters: ProjectFilters) {
  return useQuery({
    queryKey: projectKeys.list(filters),
    queryFn: () => listProjects(filters),
    placeholderData: keepPreviousData,
  })
}

export function useProject(projectId: string) {
  return useQuery({ queryKey: projectKeys.detail(projectId), queryFn: () => getProject(projectId) })
}

export function useProjectMembers(projectId: string) {
  return useQuery({
    queryKey: projectKeys.members(projectId),
    queryFn: () => listMembers(projectId),
  })
}

export function useUserSearch(q: string, enabled: boolean) {
  return useQuery({
    queryKey: ['users', 'search', q],
    queryFn: () => searchUsers(q),
    enabled,
    staleTime: 30_000,
  })
}

function useProjectCacheUpdate() {
  const queryClient = useQueryClient()
  return (project: Project) => {
    queryClient.setQueryData(projectKeys.detail(project.id), project)
    void queryClient.invalidateQueries({ queryKey: ['projects', 'list'] })
  }
}

export function useCreateProject() {
  const update = useProjectCacheUpdate()
  return useMutation({ mutationFn: createProject, onSuccess: update })
}

export function useUpdateProject(projectId: string) {
  const update = useProjectCacheUpdate()
  return useMutation({
    mutationFn: (input: Parameters<typeof updateProject>[1]) => updateProject(projectId, input),
    onSuccess: update,
  })
}

export function useArchiveProject(projectId: string) {
  const update = useProjectCacheUpdate()
  return useMutation({
    mutationFn: ({ archive, version }: { archive: boolean; version: number }) =>
      archive ? archiveProject(projectId, version) : restoreProject(projectId, version),
    onSuccess: update,
  })
}

export function useMemberMutations(projectId: string) {
  const queryClient = useQueryClient()
  const onSuccess = (members: ProjectMembers) => {
    queryClient.setQueryData(projectKeys.members(projectId), members)
    void queryClient.invalidateQueries({ queryKey: projectKeys.detail(projectId), exact: true })
    void queryClient.invalidateQueries({ queryKey: ['projects', 'list'] })
  }
  const add = useMutation({
    mutationFn: ({ userId, version }: { userId: string; version: number }) =>
      addMember(projectId, userId, version),
    onSuccess,
  })
  const remove = useMutation({
    mutationFn: ({ memberId, version }: { memberId: string; version: number }) =>
      removeMember(projectId, memberId, version),
    onSuccess,
  })
  return { add, remove }
}
