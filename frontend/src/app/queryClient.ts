import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query'

import { ApiError } from '@/services/apiClient'
import { currentUserQueryKey } from '@/services/auth'

export function createQueryClient() {
  // Um 401 em qualquer pedido significa sessão expirada: o RequireAuth redireciona para o login.
  const onError = (error: Error) => {
    if (error instanceof ApiError && error.status === 401) {
      queryClient.setQueryData(currentUserQueryKey, null)
    }
  }
  const queryClient: QueryClient = new QueryClient({
    queryCache: new QueryCache({ onError }),
    mutationCache: new MutationCache({ onError }),
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: false,
        retry: (failureCount, error) => {
          if (error instanceof ApiError && error.status < 500) return false
          return failureCount < 2
        },
      },
    },
  })
  return queryClient
}
