import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router'

import { currentUserQueryKey, getCurrentUser, logout } from '@/services/auth'

export function useCurrentUser() {
  return useQuery({
    queryKey: currentUserQueryKey,
    queryFn: getCurrentUser,
    staleTime: 5 * 60_000,
  })
}

export function useLogout() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  return useMutation({
    mutationFn: logout,
    onSettled: () => {
      // Mesmo que o pedido falhe, a sessão local é descartada.
      queryClient.clear()
      queryClient.setQueryData(currentUserQueryKey, null)
      void navigate('/login', { replace: true })
    },
  })
}

/** Evita redirecionamentos abertos: aceita apenas caminhos internos. */
export function safeRedirectPath(next: string | null): string {
  if (!next || !next.startsWith('/') || next.startsWith('//') || next.startsWith('/\\')) {
    return '/'
  }
  return next
}
