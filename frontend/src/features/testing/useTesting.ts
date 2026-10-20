import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createTestCase,
  createTestPlan,
  getTestCase,
  getTestPlan,
  listTestCases,
  listTestPlans,
  updateTestCase,
  updateTestPlan,
  type TestCase,
  type TestCaseFilters,
  type TestPlan,
  type TestPlanFilters,
} from '@/services/testing'

export const testCaseKeys = {
  list: (filters: TestCaseFilters) => ['test-cases', 'list', filters] as const,
  detail: (testCaseId: string) => ['test-cases', 'detail', testCaseId] as const,
}

export const testPlanKeys = {
  list: (filters: TestPlanFilters) => ['test-plans', 'list', filters] as const,
  detail: (testPlanId: string) => ['test-plans', 'detail', testPlanId] as const,
}

export function useTestCases(filters: TestCaseFilters, enabled = true) {
  return useQuery({
    queryKey: testCaseKeys.list(filters),
    queryFn: () => listTestCases(filters),
    placeholderData: keepPreviousData,
    enabled,
  })
}

export function useTestCase(testCaseId: string) {
  return useQuery({
    queryKey: testCaseKeys.detail(testCaseId),
    queryFn: () => getTestCase(testCaseId),
    enabled: Boolean(testCaseId),
  })
}

function useTestCaseCacheUpdate() {
  const queryClient = useQueryClient()
  return (testCase: TestCase) => {
    queryClient.setQueryData(testCaseKeys.detail(testCase.id), testCase)
    void queryClient.invalidateQueries({ queryKey: ['test-cases', 'list'] })
    // Os planos mostram o título e o estado dos casos.
    void queryClient.invalidateQueries({ queryKey: ['test-plans', 'detail'] })
  }
}

export function useCreateTestCase() {
  const update = useTestCaseCacheUpdate()
  return useMutation({ mutationFn: createTestCase, onSuccess: update })
}

export function useUpdateTestCase(testCaseId: string) {
  const update = useTestCaseCacheUpdate()
  return useMutation({
    mutationFn: (input: Parameters<typeof updateTestCase>[1]) => updateTestCase(testCaseId, input),
    onSuccess: update,
  })
}

export function useTestPlans(filters: TestPlanFilters) {
  return useQuery({
    queryKey: testPlanKeys.list(filters),
    queryFn: () => listTestPlans(filters),
    placeholderData: keepPreviousData,
  })
}

export function useTestPlan(testPlanId: string) {
  return useQuery({
    queryKey: testPlanKeys.detail(testPlanId),
    queryFn: () => getTestPlan(testPlanId),
    enabled: Boolean(testPlanId),
  })
}

function useTestPlanCacheUpdate() {
  const queryClient = useQueryClient()
  return (plan: TestPlan) => {
    queryClient.setQueryData(testPlanKeys.detail(plan.id), plan)
    void queryClient.invalidateQueries({ queryKey: ['test-plans', 'list'] })
  }
}

export function useCreateTestPlan() {
  const update = useTestPlanCacheUpdate()
  return useMutation({ mutationFn: createTestPlan, onSuccess: update })
}

export function useUpdateTestPlan(testPlanId: string) {
  const update = useTestPlanCacheUpdate()
  return useMutation({
    mutationFn: (input: Parameters<typeof updateTestPlan>[1]) => updateTestPlan(testPlanId, input),
    onSuccess: update,
  })
}
