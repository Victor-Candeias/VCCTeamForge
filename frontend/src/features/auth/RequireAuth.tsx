import { Navigate, Outlet, useLocation } from 'react-router'

import { useCurrentUser } from '@/features/auth/useAuth'

export function RequireAuth() {
  const location = useLocation()
  const { data: user, isPending, isError } = useCurrentUser()

  if (isPending) {
    return <p className="p-6 text-muted-foreground">A carregar…</p>
  }
  if (isError) {
    return <p className="p-6 text-destructive">Não foi possível contactar a API.</p>
  }
  if (!user) {
    const next = `${location.pathname}${location.search}`
    const search = next === '/' ? '' : `?next=${encodeURIComponent(next)}`
    return <Navigate to={`/login${search}`} replace />
  }
  return <Outlet />
}
