import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createTestCase,
  createTestPlan,
  createTestRun,
  createTestRunBug,
  deleteTestRunEvidence,
  getTestPlanProgress,
  getTestRun,
  listTestRunEvidences,
  listTestRuns,
  updateTestRun,
  uploadTestRunEvidence,
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
  type TestRun,
  type TestRunBugInput,
  type TestRunFilters,
  type TestRunUpdateInput,
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

export const testRunKeys = {
  list: (filters: TestRunFilters) => ['test-runs', 'list', filters] as const,
  detail: (testRunId: string) => ['test-runs', 'detail', testRunId] as const,
  evidences: (testRunId: string) => ['test-runs', 'evidences', testRunId] as const,
  progress: (testPlanId: string) => ['test-plans', 'progress', testPlanId] as const,
}

export function useTestRuns(filters: TestRunFilters) {
  return useQuery({
    queryKey: testRunKeys.list(filters),
    queryFn: () => listTestRuns(filters),
    placeholderData: keepPreviousData,
  })
}

export function useTestRun(testRunId: string) {
  return useQuery({
    queryKey: testRunKeys.detail(testRunId),
    queryFn: () => getTestRun(testRunId),
    enabled: Boolean(testRunId),
  })
}

export function useTestPlanProgress(testPlanId: string) {
  return useQuery({
    queryKey: testRunKeys.progress(testPlanId),
    queryFn: () => getTestPlanProgress(testPlanId),
    enabled: Boolean(testPlanId),
  })
}

function useTestRunCacheUpdate() {
  const queryClient = useQueryClient()
  return (run: TestRun) => {
    queryClient.setQueryData(testRunKeys.detail(run.id), run)
    void queryClient.invalidateQueries({ queryKey: ['test-runs', 'list'] })
    void queryClient.invalidateQueries({ queryKey: ['test-plans', 'progress'] })
  }
}

export function useCreateTestRun() {
  const update = useTestRunCacheUpdate()
  return useMutation({ mutationFn: createTestRun, onSuccess: update })
}

export function useUpdateTestRun(testRunId: string) {
  const update = useTestRunCacheUpdate()
  return useMutation({
    mutationFn: (input: TestRunUpdateInput) => updateTestRun(testRunId, input),
    onSuccess: update,
  })
}

export function useCreateTestRunBug(testRunId: string) {
  const update = useTestRunCacheUpdate()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: TestRunBugInput) => createTestRunBug(testRunId, input),
    onSuccess: (run) => {
      update(run)
      void queryClient.invalidateQueries({ queryKey: ['issues'] })
    },
  })
}

export function useTestRunEvidences(testRunId: string) {
  return useQuery({
    queryKey: testRunKeys.evidences(testRunId),
    queryFn: () => listTestRunEvidences(testRunId),
  })
}

export function useTestRunEvidenceMutations(testRunId: string) {
  const queryClient = useQueryClient()
  const onSuccess = () => {
    void queryClient.invalidateQueries({ queryKey: testRunKeys.evidences(testRunId) })
    void queryClient.invalidateQueries({ queryKey: testRunKeys.detail(testRunId) })
    void queryClient.invalidateQueries({ queryKey: ['test-runs', 'list'] })
  }
  return {
    upload: useMutation({
      mutationFn: (file: File) => uploadTestRunEvidence(testRunId, file),
      onSuccess,
    }),
    remove: useMutation({
      mutationFn: (evidenceId: string) => deleteTestRunEvidence(testRunId, evidenceId),
      onSuccess,
    }),
  }
}
