import { useState } from 'react'
import { Link } from 'react-router'

import { Pagination } from '@/components/Pagination'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useUpdateUser, useUsers } from '@/features/admin/useUsers'
import { useCurrentUser } from '@/features/auth/useAuth'
import { usePermission } from '@/hooks/usePermissions'
import { mutationErrorMessage } from '@/lib/errors'
import { DEFAULT_PAGE_SIZE } from '@/lib/pagination'
import { roleLabels, type Role } from '@/services/auth'
import { formatDateTime } from '@/services/common'
import { userStatusLabels, type ManagedUser, type UserStatus } from '@/services/users'

export function UserStatusBadge({ status }: { status: UserStatus }) {
  return (
    <Badge variant={status === 'active' ? 'secondary' : 'destructive'}>
      {userStatusLabels[status]}
    </Badge>
  )
}

export function UsersPage() {
  const canManage = usePermission('users:manage')
  const { data: me } = useCurrentUser()
  const [q, setQ] = useState('')
  const [role, setRole] = useState<Role | ''>('')
  const [status, setStatus] = useState<UserStatus | ''>('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE)
  const users = useUsers(
    {
      q: q.trim() || undefined,
      role: role ? [role] : undefined,
      status: status ? [status] : undefined,
      page,
      pageSize,
    },
    canManage,
  )
  const update = useUpdateUser()

  if (!canManage) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Não tem permissão para gerir utilizadores.</AlertDescription>
      </Alert>
    )
  }

  const toggleStatus = (user: ManagedUser) => {
    const next: UserStatus = user.status === 'active' ? 'disabled' : 'active'
    if (
      next === 'disabled' &&
      !window.confirm(`Desativar ${user.name}? As sessões abertas deste utilizador terminam.`)
    ) {
      return
    }
    update.mutate({ userId: user.id, version: user.version, status: next })
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-semibold">Utilizadores</h1>
        <Button asChild>
          <Link to="/admin/users/new">Novo utilizador</Link>
        </Button>
      </div>

      <div className="flex flex-wrap items-end gap-4">
        <div className="space-y-1">
          <Label htmlFor="user-search">Pesquisar</Label>
          <Input
            id="user-search"
            placeholder="Nome ou email"
            value={q}
            onChange={(event) => {
              setQ(event.target.value)
              setPage(1)
            }}
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="user-role">Perfil</Label>
          <NativeSelect
            id="user-role"
            value={role}
            onChange={(event) => {
              setRole(event.target.value as Role | '')
              setPage(1)
            }}
          >
            <option value="">Todos</option>
            {Object.entries(roleLabels).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </NativeSelect>
        </div>
        <div className="space-y-1">
          <Label htmlFor="user-status">Estado</Label>
          <NativeSelect
            id="user-status"
            value={status}
            onChange={(event) => {
              setStatus(event.target.value as UserStatus | '')
              setPage(1)
            }}
          >
            <option value="">Todos</option>
            {Object.entries(userStatusLabels).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </NativeSelect>
        </div>
      </div>

      {update.isError && (
        <Alert variant="destructive">
          <AlertDescription>{mutationErrorMessage(update.error)}</AlertDescription>
        </Alert>
      )}
      {users.isError && (
        <Alert variant="destructive">
          <AlertDescription>Não foi possível carregar os utilizadores.</AlertDescription>
        </Alert>
      )}
      {users.isPending && <p className="text-muted-foreground">A carregar…</p>}
      {users.data && users.data.items.length === 0 && (
        <p className="text-muted-foreground">Nenhum utilizador encontrado.</p>
      )}
      {users.data && users.data.items.length > 0 && (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Nome</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Perfil</TableHead>
                <TableHead>Estado</TableHead>
                <TableHead>Último acesso</TableHead>
                <TableHead className="text-right">Ações</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.data.items.map((user) => (
                <TableRow key={user.id}>
                  <TableCell>
                    <Link className="font-medium hover:underline" to={`/admin/users/${user.id}`}>
                      {user.name}
                    </Link>
                  </TableCell>
                  <TableCell>{user.email}</TableCell>
                  <TableCell>{roleLabels[user.role]}</TableCell>
                  <TableCell>
                    <UserStatusBadge status={user.status} />
                  </TableCell>
                  <TableCell className="whitespace-nowrap">
                    {formatDateTime(user.lastLoginAt)}
                  </TableCell>
                  <TableCell className="text-right">
                    {user.id !== me?.id && (
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={update.isPending}
                        onClick={() => toggleStatus(user)}
                      >
                        {user.status === 'active' ? 'Desativar' : 'Ativar'}
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Pagination
            page={users.data.page}
            pageSize={users.data.pageSize}
            total={users.data.total}
            onChange={setPage}
            onPageSizeChange={(size) => {
              setPageSize(size)
              setPage(1)
            }}
          />
        </>
      )}
    </div>
  )
}
