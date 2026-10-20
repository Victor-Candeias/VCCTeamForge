import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { Link, useNavigate, useParams } from 'react-router'
import { z } from 'zod'

import { Field } from '@/components/Field'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { useProjectContext } from '@/features/projects/projectContext'
import { useCreateSprint, useSprint, useSprints, useUpdateSprint } from '@/features/sprints/useSprints'
import { mutationErrorMessage } from '@/lib/errors'
import { ApiError } from '@/services/apiClient'
import { addDays, type Sprint } from '@/services/sprints'

const MAX_DURATION_DAYS = 60
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/

const validDates = (data: { startDate: string; endDate: string }) =>
  ISO_DATE.test(data.startDate) && ISO_DATE.test(data.endDate)

const sprintSchema = z
  .object({
    name: z.string().trim().min(1, 'Indique o nome').max(80, 'Máximo 80 caracteres'),
    goal: z.string().max(1000, 'Máximo 1000 caracteres'),
    startDate: z.iso.date('Indique a data de início'),
    endDate: z.iso.date('Indique a data de fim'),
  })
  .refine((data) => !validDates(data) || data.endDate >= data.startDate, {
    message: 'A data de fim não pode ser anterior à data de início',
    path: ['endDate'],
  })
  .refine(
    (data) => !validDates(data) || data.endDate < addDays(data.startDate, MAX_DURATION_DAYS),
    {
      message: `Um sprint dura no máximo ${MAX_DURATION_DAYS} dias`,
      path: ['endDate'],
    },
  )

type SprintFormValues = z.infer<typeof sprintSchema>

function SprintFormFields({
  defaults,
  sprint,
  durationDays,
  submitting,
  error,
  onSubmit,
}: {
  defaults: SprintFormValues
  sprint?: Sprint
  durationDays: number
  submitting: boolean
  error: unknown
  onSubmit: (values: SprintFormValues) => void
}) {
  const { project } = useProjectContext()
  const form = useForm<SprintFormValues>({
    resolver: zodResolver(sprintSchema),
    defaultValues: defaults,
  })
  const { errors } = form.formState
  const serverErrors = error instanceof ApiError ? error.fieldErrors() : {}
  const fieldError = (name: keyof SprintFormValues) => errors[name]?.message ?? serverErrors[name]
  const startLocked = sprint?.status === 'active'

  return (
    <form className="max-w-2xl space-y-4" noValidate onSubmit={form.handleSubmit(onSubmit)}>
      {error !== null && error !== undefined && (
        <Alert variant="destructive">
          <AlertDescription>{mutationErrorMessage(error)}</AlertDescription>
        </Alert>
      )}
      <Field label="Nome" htmlFor="sprint-name" error={fieldError('name')}>
        <Input
          id="sprint-name"
          aria-invalid={fieldError('name') ? true : undefined}
          {...form.register('name')}
        />
      </Field>
      <Field label="Objetivo" htmlFor="sprint-goal" error={fieldError('goal')}>
        <Textarea id="sprint-goal" rows={3} {...form.register('goal')} />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Data de início" htmlFor="sprint-start" error={fieldError('startDate')}>
          <Input
            id="sprint-start"
            type="date"
            readOnly={startLocked}
            aria-invalid={fieldError('startDate') ? true : undefined}
            {...form.register('startDate', {
              onChange: (event: { target: { value: string } }) => {
                const value = event.target.value
                // Enquanto o fim não for escolhido à mão, acompanha a duração do projeto.
                if (!sprint && value && !form.getFieldState('endDate').isDirty) {
                  form.setValue('endDate', addDays(value, durationDays - 1))
                }
              },
            })}
          />
        </Field>
        <Field label="Data de fim" htmlFor="sprint-end" error={fieldError('endDate')}>
          <Input
            id="sprint-end"
            type="date"
            aria-invalid={fieldError('endDate') ? true : undefined}
            {...form.register('endDate')}
          />
        </Field>
      </div>
      {startLocked && (
        <p className="text-sm text-muted-foreground">
          O sprint está ativo: a data de início já não pode ser alterada.
        </p>
      )}
      <div className="flex gap-2">
        <Button type="submit" disabled={submitting}>
          {submitting ? 'A guardar…' : sprint ? 'Guardar alterações' : 'Criar sprint'}
        </Button>
        <Button variant="outline" asChild>
          <Link to={`/projects/${project.id}/sprints`}>Cancelar</Link>
        </Button>
      </div>
    </form>
  )
}

function today(): string {
  return new Date().toISOString().slice(0, 10)
}

export function SprintCreatePage() {
  const { project } = useProjectContext()
  const navigate = useNavigate()
  const mutation = useCreateSprint()
  // O sprint mais recente (ordem por omissão: -startDate) sugere o nome e as datas seguintes.
  const latest = useSprints({ projectId: project.id, page: 1, pageSize: 1 })
  const durationDays = project.settings.sprintDurationDays

  if (latest.isPending) return <p className="text-muted-foreground">A carregar…</p>
  if (project.status === 'archived') {
    return (
      <Alert>
        <AlertDescription>Projeto arquivado: não é possível criar sprints.</AlertDescription>
      </Alert>
    )
  }

  const previous = latest.data?.items[0]
  const nextStart =
    previous && addDays(previous.endDate, 1) > today() ? addDays(previous.endDate, 1) : today()
  const defaults: SprintFormValues = {
    name: `Sprint ${(latest.data?.total ?? 0) + 1}`,
    goal: '',
    startDate: nextStart,
    endDate: addDays(nextStart, durationDays - 1),
  }

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">Novo sprint</h2>
      <SprintFormFields
        defaults={defaults}
        durationDays={durationDays}
        submitting={mutation.isPending}
        error={mutation.error}
        onSubmit={(values) =>
          mutation.mutate(
            { projectId: project.id, ...values },
            { onSuccess: () => void navigate(`/projects/${project.id}/sprints`) },
          )
        }
      />
    </div>
  )
}

export function SprintEditPage() {
  const { project } = useProjectContext()
  const { sprintId = '' } = useParams()
  const navigate = useNavigate()
  const sprint = useSprint(sprintId)
  const mutation = useUpdateSprint(sprintId)

  if (sprint.isPending) return <p className="text-muted-foreground">A carregar…</p>
  if (sprint.isError || sprint.data.projectId !== project.id) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Sprint não encontrado ou sem acesso.</AlertDescription>
      </Alert>
    )
  }
  if (!sprint.data.canEdit) {
    return (
      <Alert>
        <AlertDescription>Não é possível editar este sprint.</AlertDescription>
      </Alert>
    )
  }

  const data = sprint.data
  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">Editar {data.name}</h2>
      <SprintFormFields
        sprint={data}
        defaults={{
          name: data.name,
          goal: data.goal,
          startDate: data.startDate,
          endDate: data.endDate,
        }}
        durationDays={data.durationDays}
        submitting={mutation.isPending}
        error={mutation.error}
        onSubmit={(values) => {
          const { startDate, ...rest } = values
          mutation.mutate(
            {
              ...rest,
              ...(data.status === 'planned' ? { startDate } : {}),
              version: data.version,
            },
            { onSuccess: () => void navigate(`/projects/${project.id}/sprints`) },
          )
        }}
      />
    </div>
  )
}
