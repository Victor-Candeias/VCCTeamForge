import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createUser,
  getUser,
  listUsers,
  resetUserPassword,
  updateUser,
  type ManagedUser,
  type UserFilters,
  type UserUpdateInput,
} from '@/services/users'

export const userKeys = {
  list: (filters: UserFilters) => ['admin-users', 'list', filters] as const,
  detail: (userId: string) => ['admin-users', 'detail', userId] as const,
}

export function useUsers(filters: UserFilters, enabled = true) {
  return useQuery({
    queryKey: userKeys.list(filters),
    queryFn: () => listUsers(filters),
    placeholderData: keepPreviousData,
    enabled,
  })
}

export function useUser(userId: string) {
  return useQuery({
    queryKey: userKeys.detail(userId),
    queryFn: () => getUser(userId),
    enabled: Boolean(userId),
  })
}

function useUserCacheUpdate() {
  const queryClient = useQueryClient()
  return (user: ManagedUser) => {
    queryClient.setQueryData(userKeys.detail(user.id), user)
    void queryClient.invalidateQueries({ queryKey: ['admin-users', 'list'] })
    // Os seletores de membros/responsáveis usam a pesquisa de utilizadores ativos.
    void queryClient.invalidateQueries({ queryKey: ['users', 'search'] })
  }
}

export function useCreateUser() {
  const update = useUserCacheUpdate()
  return useMutation({ mutationFn: createUser, onSuccess: update })
}

export function useUpdateUser() {
  const update = useUserCacheUpdate()
  return useMutation({
    mutationFn: ({ userId, ...input }: UserUpdateInput & { userId: string }) =>
      updateUser(userId, input),
    onSuccess: update,
  })
}

export function useResetPassword(userId: string) {
  const update = useUserCacheUpdate()
  return useMutation({
    mutationFn: (input: { version: number; password: string }) =>
      resetUserPassword(userId, input),
    onSuccess: update,
  })
}
