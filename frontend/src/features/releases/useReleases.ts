import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createRelease,
  getRelease,
  listReleases,
  transitionRelease,
  updateRelease,
  type Release,
  type ReleaseFilters,
  type ReleaseTransitionInput,
} from '@/services/releases'

export const releaseKeys = {
  list: (filters: ReleaseFilters) => ['releases', 'list', filters] as const,
  detail: (releaseId: string) => ['releases', 'detail', releaseId] as const,
}

export function useReleases(filters: ReleaseFilters) {
  return useQuery({
    queryKey: releaseKeys.list(filters),
    queryFn: () => listReleases(filters),
    placeholderData: keepPreviousData,
  })
}

export function useRelease(releaseId: string) {
  return useQuery({
    queryKey: releaseKeys.detail(releaseId),
    queryFn: () => getRelease(releaseId),
    enabled: Boolean(releaseId),
  })
}

function useReleaseCacheUpdate() {
  const queryClient = useQueryClient()
  return (release: Release) => {
    queryClient.setQueryData(releaseKeys.detail(release.id), release)
    void queryClient.invalidateQueries({ queryKey: ['releases', 'list'] })
  }
}

export function useCreateRelease() {
  const update = useReleaseCacheUpdate()
  return useMutation({ mutationFn: createRelease, onSuccess: update })
}

export function useUpdateRelease(releaseId: string) {
  const update = useReleaseCacheUpdate()
  return useMutation({
    mutationFn: (input: Parameters<typeof updateRelease>[1]) => updateRelease(releaseId, input),
    onSuccess: update,
  })
}

export function useTransitionRelease(releaseId: string) {
  const update = useReleaseCacheUpdate()
  return useMutation({
    mutationFn: (input: ReleaseTransitionInput) => transitionRelease(releaseId, input),
    onSuccess: update,
  })
}
