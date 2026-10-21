import { useState } from 'react'
import {
  FolderKanban,
  LayoutDashboard,
  LogOut,
  Menu,
  ScrollText,
  Users,
  X,
  type LucideIcon,
} from 'lucide-react'
import { NavLink, Outlet } from 'react-router'

import { BrandLogo } from '@/components/BrandLogo'
import { Button } from '@/components/ui/button'
import { useCurrentUser, useLogout } from '@/features/auth/useAuth'
import { usePermission } from '@/hooks/usePermissions'
import { cn } from '@/lib/utils'
import { roleLabels } from '@/services/auth'

interface NavigationItem {
  to: string
  label: string
  end: boolean
  icon: LucideIcon
}

const navigation: NavigationItem[] = [
  { to: '/', label: 'Dashboard', end: true, icon: LayoutDashboard },
  { to: '/projects', label: 'Projetos', end: false, icon: FolderKanban },
]

const usersNavigation: NavigationItem = {
  to: '/admin/users',
  label: 'Utilizadores',
  end: false,
  icon: Users,
}
const auditNavigation: NavigationItem = {
  to: '/admin/audit',
  label: 'Auditoria',
  end: false,
  icon: ScrollText,
}

function initials(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  const letters = parts.length > 1 ? [parts[0][0], parts[parts.length - 1][0]] : [parts[0]?.[0]]
  return letters.join('').toUpperCase()
}

export function AppLayout() {
  const { data: user } = useCurrentUser()
  const logout = useLogout()
  const canManageUsers = usePermission('users:manage')
  const canReadAudit = usePermission('audit:read')
  const [menuOpen, setMenuOpen] = useState(false)
  const administration = [
    ...(canManageUsers ? [usersNavigation] : []),
    ...(canReadAudit ? [auditNavigation] : []),
  ]

  const renderItem = (item: NavigationItem) => (
    <NavLink
      key={item.to}
      to={item.to}
      end={item.end}
      onClick={() => setMenuOpen(false)}
      className={({ isActive }) =>
        cn(
          'group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium',
          'transition-colors',
          'text-sidebar-foreground/75 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground',
          isActive && 'bg-sidebar-accent text-sidebar-accent-foreground',
        )
      }
    >
      {({ isActive }) => (
        <>
          <item.icon
            aria-hidden="true"
            className={cn(
              'size-4 text-sidebar-foreground/60 group-hover:text-sidebar-accent-foreground',
              isActive && 'text-sidebar-primary group-hover:text-sidebar-primary',
            )}
          />
          {item.label}
        </>
      )}
    </NavLink>
  )

  return (
    <div className="min-h-svh bg-background text-foreground">
      <header
        className={cn(
          'sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-sidebar-border',
          'bg-sidebar px-4 text-sidebar-accent-foreground lg:hidden',
        )}
      >
        <Button
          variant="ghost"
          size="icon"
          className={cn(
            'text-sidebar-foreground',
            'hover:bg-sidebar-accent hover:text-sidebar-accent-foreground',
          )}
          aria-label={menuOpen ? 'Fechar menu' : 'Abrir menu'}
          aria-expanded={menuOpen}
          aria-controls="app-sidebar"
          onClick={() => setMenuOpen((open) => !open)}
        >
          {menuOpen ? <X /> : <Menu />}
        </Button>
        <BrandLogo />
      </header>

      {menuOpen && (
        <div
          aria-hidden="true"
          className="fixed inset-0 z-30 bg-black/40 lg:hidden"
          onClick={() => setMenuOpen(false)}
        />
      )}

      <aside
        id="app-sidebar"
        className={cn(
          'fixed inset-y-0 left-0 z-40 flex w-64 flex-col bg-sidebar text-sidebar-foreground',
          'transition-[translate,visibility] duration-200 lg:visible lg:translate-x-0',
          menuOpen ? 'translate-x-0' : 'invisible -translate-x-full',
        )}
      >
        <div className="flex h-16 items-center px-5 text-sidebar-accent-foreground">
          <BrandLogo />
        </div>
        <nav
          aria-label="Navegação principal"
          className="scrollbar-thin flex-1 overflow-y-auto px-3 py-2"
        >
          <div className="space-y-1">{navigation.map(renderItem)}</div>
          {administration.length > 0 && (
            <div className="mt-6">
              <p
                className={cn(
                  'px-3 pb-2 text-xs font-semibold tracking-wider uppercase',
                  'text-sidebar-foreground/50',
                )}
              >
                Administração
              </p>
              <div className="space-y-1">{administration.map(renderItem)}</div>
            </div>
          )}
        </nav>
        {user && (
          <div className="border-t border-sidebar-border p-3">
            <div className="flex items-center gap-3 rounded-lg px-2 py-2">
              <span
                aria-hidden="true"
                className={cn(
                  'flex size-9 shrink-0 items-center justify-center rounded-full',
                  'bg-sidebar-primary text-sm font-semibold text-sidebar-primary-foreground',
                )}
              >
                {initials(user.name)}
              </span>
              <div className="min-w-0 flex-1 text-sm">
                <p className="truncate font-medium text-sidebar-accent-foreground">{user.name}</p>
                <p className="truncate text-xs text-sidebar-foreground/60">
                  {roleLabels[user.role]}
                </p>
              </div>
            </div>
            <Button
              variant="ghost"
              size="sm"
              className={cn(
                'mt-1 w-full justify-start gap-2 text-sidebar-foreground/75',
                'hover:bg-sidebar-accent hover:text-sidebar-accent-foreground',
              )}
              disabled={logout.isPending}
              onClick={() => logout.mutate()}
            >
              <LogOut aria-hidden="true" />
              Terminar sessão
            </Button>
          </div>
        )}
      </aside>

      <div className="lg:pl-64">
        <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
