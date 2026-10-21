import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate, useParams } from 'react-router'
import { z } from 'zod'

import { Field } from '@/components/Field'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { NativeSelect } from '@/components/ui/native-select'
import { useCreateUser, useResetPassword, useUpdateUser, useUser } from '@/features/admin/useUsers'
import { UserStatusBadge } from '@/features/admin/UsersPage'
import { useCurrentUser } from '@/features/auth/useAuth'
import { usePermission } from '@/hooks/usePermissions'
import { mutationErrorMessage } from '@/lib/errors'
import { ApiError } from '@/services/apiClient'
import { roleLabels, type Role } from '@/services/auth'
import { formatDateTime } from '@/services/common'
import { userStatusLabels, type ManagedUser, type UserStatus } from '@/services/users'

const PASSWORD_MIN_LENGTH = 12
const PASSWORD_MAX_LENGTH = 128

const roles = Object.keys(roleLabels) as Role[]

const passwordFields = {
  password: z
    .string()
    .min(PASSWORD_MIN_LENGTH, `Mínimo ${PASSWORD_MIN_LENGTH} caracteres`)
    .max(PASSWORD_MAX_LENGTH, `Máximo ${PASSWORD_MAX_LENGTH} caracteres`),
  confirmPassword: z.string(),
}

const passwordsMatch = {
  check: (data: { password: string; confirmPassword: string }) =>
    data.password === data.confirmPassword,
  options: { message: 'As passwords não coincidem', path: ['confirmPassword'] },
}

const profileFields = {
  name: z.string().trim().min(1, 'Indique o nome').max(120),
  email: z.string().trim().max(254).pipe(z.email('Email inválido')),
  role: z.enum(['admin', 'tech_lead', 'developer', 'qa']),
}

const createSchema = z
  .object({ ...profileFields, ...passwordFields })
  .refine(passwordsMatch.check, passwordsMatch.options)

const editSchema = z.object({ ...profileFields, status: z.enum(['active', 'disabled']) })

const passwordSchema = z
  .object(passwordFields)
  .refine(passwordsMatch.check, passwordsMatch.options)

type CreateValues = z.infer<typeof createSchema>
type EditValues = z.infer<typeof editSchema>
type PasswordValues = z.infer<typeof passwordSchema>

function serverFieldErrors(error: unknown): Record<string, string> {
  return error instanceof ApiError ? error.fieldErrors() : {}
}

function MutationError({ error }: { error: unknown }) {
  if (error === null || error === undefined) return null
  return (
    <Alert variant="destructive">
      <AlertDescription>{mutationErrorMessage(error)}</AlertDescription>
    </Alert>
  )
}

function NoPermission() {
  return (
    <Alert variant="destructive">
      <AlertDescription>Não tem permissão para gerir utilizadores.</AlertDescription>
    </Alert>
  )
}

export function UserCreatePage() {
  const canManage = usePermission('users:manage')
  const navigate = useNavigate()
  const mutation = useCreateUser()
  const form = useForm<CreateValues>({
    resolver: zodResolver(createSchema),
    defaultValues: { name: '', email: '', role: 'developer', password: '', confirmPassword: '' },
  })
  if (!canManage) return <NoPermission />

  const { errors } = form.formState
  const server = serverFieldErrors(mutation.error)
  const fieldError = (name: keyof CreateValues) => errors[name]?.message ?? server[name]

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Novo utilizador</h1>
      <form
        className="max-w-xl space-y-4"
        noValidate
        onSubmit={form.handleSubmit(({ name, email, role, password }) =>
          mutation.mutate(
            { name, email, role, password },
            { onSuccess: () => void navigate('/admin/users') },
          ),
        )}
      >
        <MutationError error={mutation.error} />
        <Field label="Nome" htmlFor="name" error={fieldError('name')}>
          <Input id="name" autoComplete="off" {...form.register('name')} />
        </Field>
        <Field label="Email" htmlFor="email" error={fieldError('email')}>
          <Input id="email" type="email" autoComplete="off" {...form.register('email')} />
        </Field>
        <Field label="Perfil" htmlFor="role" error={fieldError('role')}>
          <NativeSelect id="role" {...form.register('role')}>
            {roles.map((value) => (
              <option key={value} value={value}>
                {roleLabels[value]}
              </option>
            ))}
          </NativeSelect>
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Password" htmlFor="password" error={fieldError('password')}>
            <Input
              id="password"
              type="password"
              autoComplete="new-password"
              {...form.register('password')}
            />
          </Field>
          <Field
            label="Confirmar password"
            htmlFor="confirmPassword"
            error={fieldError('confirmPassword')}
          >
            <Input
              id="confirmPassword"
              type="password"
              autoComplete="new-password"
              {...form.register('confirmPassword')}
            />
          </Field>
        </div>
        <div className="flex gap-2">
          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? 'A guardar…' : 'Criar utilizador'}
          </Button>
          <Button variant="outline" asChild>
            <Link to="/admin/users">Cancelar</Link>
          </Button>
        </div>
      </form>
    </div>
  )
}

function UserEditForm({ user, isSelf }: { user: ManagedUser; isSelf: boolean }) {
  const navigate = useNavigate()
  const mutation = useUpdateUser()
  const form = useForm<EditValues>({
    resolver: zodResolver(editSchema),
    defaultValues: { name: user.name, email: user.email, role: user.role, status: user.status },
  })
  const { errors } = form.formState
  const server = serverFieldErrors(mutation.error)
  const fieldError = (name: keyof EditValues) => errors[name]?.message ?? server[name]

  return (
    <form
      className="max-w-xl space-y-4"
      noValidate
      onSubmit={form.handleSubmit((values) =>
        mutation.mutate(
          { userId: user.id, version: user.version, ...values },
          { onSuccess: () => void navigate('/admin/users') },
        ),
      )}
    >
      <MutationError error={mutation.error} />
      <Field label="Nome" htmlFor="name" error={fieldError('name')}>
        <Input id="name" autoComplete="off" {...form.register('name')} />
      </Field>
      <Field label="Email" htmlFor="email" error={fieldError('email')}>
        <Input id="email" type="email" autoComplete="off" {...form.register('email')} />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Perfil" htmlFor="role" error={fieldError('role')}>
          <NativeSelect id="role" disabled={isSelf} {...form.register('role')}>
            {roles.map((value) => (
              <option key={value} value={value}>
                {roleLabels[value]}
              </option>
            ))}
          </NativeSelect>
        </Field>
        <Field label="Estado" htmlFor="status" error={fieldError('status')}>
          <NativeSelect id="status" disabled={isSelf} {...form.register('status')}>
            {(Object.keys(userStatusLabels) as UserStatus[]).map((value) => (
              <option key={value} value={value}>
                {userStatusLabels[value]}
              </option>
            ))}
          </NativeSelect>
        </Field>
      </div>
      {isSelf && (
        <p className="text-sm text-muted-foreground">
          Não pode alterar o seu próprio perfil nem desativar a sua conta.
        </p>
      )}
      <div className="flex gap-2">
        <Button type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? 'A guardar…' : 'Guardar alterações'}
        </Button>
        <Button variant="outline" asChild>
          <Link to="/admin/users">Cancelar</Link>
        </Button>
      </div>
    </form>
  )
}

function PasswordResetForm({ user }: { user: ManagedUser }) {
  const mutation = useResetPassword(user.id)
  const [done, setDone] = useState(false)
  const form = useForm<PasswordValues>({
    resolver: zodResolver(passwordSchema),
    defaultValues: { password: '', confirmPassword: '' },
  })
  const { errors } = form.formState
  const server = serverFieldErrors(mutation.error)
  const fieldError = (name: keyof PasswordValues) => errors[name]?.message ?? server[name]

  return (
    <form
      className="max-w-xl space-y-4"
      noValidate
      onSubmit={form.handleSubmit(({ password }) => {
        setDone(false)
        mutation.mutate(
          { version: user.version, password },
          {
            onSuccess: () => {
              setDone(true)
              form.reset()
            },
          },
        )
      })}
    >
      <h2 className="text-lg font-semibold">Redefinir password</h2>
      <p className="text-sm text-muted-foreground">
        As sessões abertas deste utilizador terminam e terá de entrar com a nova password.
      </p>
      <MutationError error={mutation.error} />
      {done && (
        <Alert>
          <AlertDescription>Password redefinida.</AlertDescription>
        </Alert>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Nova password" htmlFor="newPassword" error={fieldError('password')}>
          <Input
            id="newPassword"
            type="password"
            autoComplete="new-password"
            {...form.register('password')}
          />
        </Field>
        <Field
          label="Confirmar nova password"
          htmlFor="confirmNewPassword"
          error={fieldError('confirmPassword')}
        >
          <Input
            id="confirmNewPassword"
            type="password"
            autoComplete="new-password"
            {...form.register('confirmPassword')}
          />
        </Field>
      </div>
      <Button type="submit" variant="outline" disabled={mutation.isPending}>
        {mutation.isPending ? 'A redefinir…' : 'Redefinir password'}
      </Button>
    </form>
  )
}

export function UserEditPage() {
  const canManage = usePermission('users:manage')
  const { userId = '' } = useParams()
  const { data: me } = useCurrentUser()
  const user = useUser(canManage ? userId : '')

  if (!canManage) return <NoPermission />
  if (user.isPending) return <p className="text-muted-foreground">A carregar…</p>
  if (user.isError) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Utilizador não encontrado.</AlertDescription>
      </Alert>
    )
  }

  return (
    <div className="space-y-8">
      <div className="space-y-1">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold">{user.data.name}</h1>
          <UserStatusBadge status={user.data.status} />
        </div>
        <p className="text-sm text-muted-foreground">
          Criado em {formatDateTime(user.data.createdAt)} · Último acesso{' '}
          {formatDateTime(user.data.lastLoginAt)}
        </p>
      </div>
      {/* A chave recria o formulário quando a versão muda (ex.: após redefinir a password). */}
      <UserEditForm key={user.data.version} user={user.data} isSelf={user.data.id === me?.id} />
      <PasswordResetForm user={user.data} />
    </div>
  )
}
