import { useCurrentUser } from '@/features/auth/useAuth'
import type { CurrentUser } from '@/services/auth'

export function hasPermission(user: CurrentUser | null | undefined, permission: string): boolean {
  return Boolean(user?.permissions.includes(permission))
}

/** Indica se o utilizador autenticado tem a permissão global (a API valida sempre). */
export function usePermission(permission: string): boolean {
  const { data: user } = useCurrentUser()
  return hasPermission(user, permission)
}
