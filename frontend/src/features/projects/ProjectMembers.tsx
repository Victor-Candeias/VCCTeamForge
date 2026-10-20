import { useState } from 'react'

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
import { useProjectContext } from '@/features/projects/projectContext'
import {
  useMemberMutations,
  useProjectMembers,
  useUserSearch,
} from '@/features/projects/useProjects'
import { mutationErrorMessage } from '@/lib/errors'
import { roleLabels } from '@/services/auth'

export function ProjectMembers() {
  const { project } = useProjectContext()
  const members = useProjectMembers(project.id)
  const { add, remove } = useMemberMutations(project.id)
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState('')
  const canManage = Boolean(members.data?.canManage) && project.status !== 'archived'
  const users = useUserSearch(query.trim(), canManage)

  if (members.isPending) return <p className="text-muted-foreground">A carregar…</p>
  if (members.isError) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Não foi possível carregar os membros.</AlertDescription>
      </Alert>
    )
  }

  const memberIds = new Set(members.data.members.map((member) => member.id))
  const candidates = (users.data ?? []).filter((user) => !memberIds.has(user.id))
  const error = add.error ?? remove.error

  return (
    <div className="space-y-4">
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{mutationErrorMessage(error)}</AlertDescription>
        </Alert>
      )}
      {canManage && (
        <form
          className="flex flex-wrap items-end gap-2"
          onSubmit={(event) => {
            event.preventDefault()
            if (!selected) return
            add.mutate(
              { userId: selected, version: members.data.version },
              { onSuccess: () => setSelected('') },
            )
          }}
        >
          <div className="space-y-1">
            <Label htmlFor="member-search">Pesquisar utilizador</Label>
            <Input
              id="member-search"
              value={query}
              placeholder="Nome ou email"
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>
          <div className="min-w-56 space-y-1">
            <Label htmlFor="member-select">Utilizador</Label>
            <NativeSelect
              id="member-select"
              value={selected}
              onChange={(event) => setSelected(event.target.value)}
            >
              <option value="">Selecionar…</option>
              {candidates.map((user) => (
                <option key={user.id} value={user.id}>
                  {user.name} ({user.email})
                </option>
              ))}
            </NativeSelect>
          </div>
          <Button type="submit" disabled={!selected || add.isPending}>
            Adicionar membro
          </Button>
        </form>
      )}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Nome</TableHead>
            <TableHead>Email</TableHead>
            <TableHead>Perfil</TableHead>
            {canManage && <TableHead className="w-24" />}
          </TableRow>
        </TableHeader>
        <TableBody>
          {members.data.members.map((member) => (
            <TableRow key={member.id}>
              <TableCell>
                {member.name} {member.isLead && <Badge variant="outline">Responsável</Badge>}
              </TableCell>
              <TableCell>{member.email}</TableCell>
              <TableCell>{roleLabels[member.role]}</TableCell>
              {canManage && (
                <TableCell>
                  {!member.isLead && (
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={remove.isPending}
                      aria-label={`Remover ${member.name}`}
                      onClick={() =>
                        remove.mutate({ memberId: member.id, version: members.data.version })
                      }
                    >
                      Remover
                    </Button>
                  )}
                </TableCell>
              )}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
