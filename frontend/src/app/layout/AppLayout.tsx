import { NavLink, Outlet } from 'react-router'

import { Button } from '@/components/ui/button'
import { useCurrentUser, useLogout } from '@/features/auth/useAuth'
import { usePermission } from '@/hooks/usePermissions'
import { cn } from '@/lib/utils'
import { roleLabels } from '@/services/auth'

const navigation = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/projects', label: 'Projetos', end: false },
]

const usersNavigation = { to: '/admin/users', label: 'Utilizadores', end: false }
const auditNavigation = { to: '/admin/audit', label: 'Auditoria', end: false }

export function AppLayout() {
  const { data: user } = useCurrentUser()
  const logout = useLogout()
  const canManageUsers = usePermission('users:manage')
  const canReadAudit = usePermission('audit:read')
  const items = [
    ...navigation,
    ...(canManageUsers ? [usersNavigation] : []),
    ...(canReadAudit ? [auditNavigation] : []),
  ]

  return (
    <div className="min-h-svh bg-background text-foreground">
      <header className="border-b">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-6 px-4">
          <span className="font-semibold">VCCTeamForge</span>
          <nav className="flex gap-4 text-sm">
            {items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  cn('text-muted-foreground hover:text-foreground', isActive && 'text-foreground')
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          {user && (
            <div className="ml-auto flex items-center gap-3 text-sm">
              <span>
                {user.name}{' '}
                <span className="text-muted-foreground">· {roleLabels[user.role]}</span>
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={logout.isPending}
                onClick={() => logout.mutate()}
              >
                Terminar sessão
              </Button>
            </div>
          )}
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
