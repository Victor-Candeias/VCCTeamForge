import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { Navigate, useNavigate, useSearchParams } from 'react-router'
import { z } from 'zod'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { safeRedirectPath, useCurrentUser } from '@/features/auth/useAuth'
import { ApiError } from '@/services/apiClient'
import { currentUserQueryKey, login } from '@/services/auth'

const loginSchema = z.object({
  email: z.email('Indique um email válido'),
  password: z.string().min(1, 'Indique a password').max(128),
})

type LoginForm = z.infer<typeof loginSchema>

function errorMessage(error: unknown) {
  if (error instanceof ApiError && (error.status === 401 || error.status === 429)) {
    return error.message
  }
  return 'Não foi possível iniciar sessão. Tente novamente.'
}

export function LoginPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const currentUser = useCurrentUser()
  const next = safeRedirectPath(searchParams.get('next'))

  const form = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: '', password: '' },
  })
  const mutation = useMutation({
    mutationFn: login,
    onSuccess: (user) => {
      queryClient.setQueryData(currentUserQueryKey, user)
      void navigate(next, { replace: true })
    },
    onError: () => form.resetField('password'),
  })

  if (currentUser.data && !mutation.isPending) {
    return <Navigate to={next} replace />
  }

  const { errors } = form.formState

  return (
    <div className="flex min-h-svh items-center justify-center bg-muted/40 p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-xl">VCCTeamForge</CardTitle>
          <CardDescription>Inicie sessão com a sua conta.</CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="space-y-4"
            noValidate
            onSubmit={form.handleSubmit((values) => mutation.mutate(values))}
          >
            {mutation.isError && (
              <Alert variant="destructive">
                <AlertDescription>{errorMessage(mutation.error)}</AlertDescription>
              </Alert>
            )}
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                autoComplete="username"
                autoFocus
                aria-invalid={errors.email ? true : undefined}
                {...form.register('email')}
              />
              {errors.email && <p className="text-sm text-destructive">{errors.email.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                aria-invalid={errors.password ? true : undefined}
                {...form.register('password')}
              />
              {errors.password && (
                <p className="text-sm text-destructive">{errors.password.message}</p>
              )}
            </div>
            <Button type="submit" className="w-full" disabled={mutation.isPending}>
              {mutation.isPending ? 'A entrar…' : 'Entrar'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
