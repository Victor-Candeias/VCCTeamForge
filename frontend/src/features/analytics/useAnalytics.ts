import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createReportSnapshot,
  exportReport,
  getDashboardOverview,
  getProjectMetrics,
  type ExportFormat,
  type MetricsParams,
} from '@/services/analytics'
import { saveDownloadedFile } from '@/services/apiClient'

export const analyticsKeys = {
  all: ['analytics'] as const,
  overview: (projectId?: string) => [...analyticsKeys.all, 'overview', projectId ?? null] as const,
  metrics: (projectId: string, params: MetricsParams) =>
    [...analyticsKeys.all, 'metrics', projectId, params] as const,
}

export function useDashboardOverview(enabled: boolean, projectId?: string) {
  return useQuery({
    queryKey: analyticsKeys.overview(projectId),
    queryFn: () => getDashboardOverview(projectId),
    // Agrega dados alterados noutras páginas: recarrega sempre que abre.
    staleTime: 0,
    enabled,
  })
}

export function useProjectMetrics(projectId: string, params: MetricsParams) {
  return useQuery({
    queryKey: analyticsKeys.metrics(projectId, params),
    queryFn: () => getProjectMetrics(projectId, params),
    staleTime: 0,
    placeholderData: keepPreviousData,
  })
}

export function useCreateReportSnapshot(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => createReportSnapshot(projectId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: analyticsKeys.all }),
  })
}

export function useExportReport(projectId: string) {
  return useMutation({
    mutationFn: ({ format, params }: { format: ExportFormat; params: MetricsParams }) =>
      exportReport(projectId, format, params),
    onSuccess: saveDownloadedFile,
  })
}
