import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { Navigate, useNavigate, useSearchParams } from 'react-router'
import { z } from 'zod'

import { CheckCircle2 } from 'lucide-react'

import { BrandLogo, BrandMark } from '@/components/BrandLogo'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { safeRedirectPath, useCurrentUser } from '@/features/auth/useAuth'
import { cn } from '@/lib/utils'
import { ApiError } from '@/services/apiClient'
import { currentUserQueryKey, login } from '@/services/auth'

const loginSchema = z.object({
  email: z.email('Indique um email válido'),
  password: z.string().min(1, 'Indique a password').max(128),
})

type LoginForm = z.infer<typeof loginSchema>

const highlights = [
  'Projetos, backlog e quadro Kanban',
  'Sprints, releases e planos de testes',
  'Métricas e relatórios da equipa',
]

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
    <div className="grid min-h-svh lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <div
        className={cn(
          'relative hidden overflow-hidden bg-sidebar p-10 text-sidebar-accent-foreground lg:flex',
          'flex-col justify-between',
        )}
      >
        <div aria-hidden="true" className="brand-glow pointer-events-none absolute inset-0" />
        <BrandLogo className="relative text-lg" />
        <div className="relative max-w-md space-y-4">
          <h2 className="text-3xl font-semibold tracking-tight">
            Planeie, acompanhe e entregue com a sua equipa.
          </h2>
          <ul className="space-y-2 text-sm text-sidebar-foreground">
            {highlights.map((item) => (
              <li key={item} className="flex items-center gap-2">
                <CheckCircle2 aria-hidden="true" className="size-4 text-sidebar-primary" />
                {item}
              </li>
            ))}
          </ul>
        </div>
      </div>
      <div className="flex items-center justify-center bg-background p-4 sm:p-8">
        <Card className="w-full max-w-sm border-0 shadow-none sm:border sm:shadow-lg">
          <CardHeader>
            <BrandMark className="mb-2 lg:hidden" />
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
    </div>
  )
}
