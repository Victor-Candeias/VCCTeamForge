import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { Link, useNavigate, useParams } from 'react-router'
import { z } from 'zod'

import { Field } from '@/components/Field'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { NativeSelect } from '@/components/ui/native-select'
import { Textarea } from '@/components/ui/textarea'
import {
  useCreateProject,
  useProject,
  useUpdateProject,
  useUserSearch,
} from '@/features/projects/useProjects'
import { mutationErrorMessage } from '@/lib/errors'
import { ApiError } from '@/services/apiClient'
import { priorityLabels, type Priority } from '@/services/common'
import { projectStatusLabels, type Project } from '@/services/projects'

const optionalDate = z.union([z.literal(''), z.iso.date('Data inválida')])

const projectSchema = z
  .object({
    key: z
      .string()
      .trim()
      .regex(/^[A-Z][A-Z0-9]{1,9}$/, 'Use 2 a 10 maiúsculas/dígitos, a começar por letra'),
    name: z.string().trim().min(1, 'Indique o nome').max(120),
    description: z.string().max(5000),
    status: z.enum(['active', 'on_hold', 'completed']),
    priority: z.enum(['low', 'medium', 'high', 'critical']),
    leadUserId: z.string(),
    startDate: optionalDate,
    targetDate: optionalDate,
    sprintDurationDays: z.coerce
      .number<string>()
      .int('Indique um número inteiro')
      .min(1, 'Mínimo 1 dia')
      .max(60, 'Máximo 60 dias'),
  })
  .refine((data) => !data.startDate || !data.targetDate || data.targetDate >= data.startDate, {
    message: 'A data alvo não pode ser anterior à data de início',
    path: ['targetDate'],
  })

type ProjectFormInput = z.input<typeof projectSchema>
type ProjectFormValues = z.output<typeof projectSchema>

const LEAD_ROLES = new Set(['admin', 'tech_lead'])

function defaultsFrom(project?: Project): ProjectFormInput {
  return {
    key: project?.key ?? '',
    name: project?.name ?? '',
    description: project?.description ?? '',
    status: project && project.status !== 'archived' ? project.status : 'active',
    priority: project?.priority ?? 'medium',
    leadUserId: project?.lead?.id ?? '',
    startDate: project?.startDate ?? '',
    targetDate: project?.targetDate ?? '',
    sprintDurationDays: String(project?.settings.sprintDurationDays ?? 14),
  }
}

function ProjectFormFields({
  project,
  submitting,
  error,
  onSubmit,
}: {
  project?: Project
  submitting: boolean
  error: unknown
  onSubmit: (values: ProjectFormValues) => void
}) {
  const isEdit = Boolean(project)
  const form = useForm<ProjectFormInput, unknown, ProjectFormValues>({
    resolver: zodResolver(projectSchema),
    defaultValues: defaultsFrom(project),
  })
  const users = useUserSearch('', true)
  const leads = (users.data ?? []).filter((user) => LEAD_ROLES.has(user.role))
  const { errors } = form.formState
  const serverErrors = error instanceof ApiError ? error.fieldErrors() : {}
  const fieldError = (name: keyof ProjectFormInput) =>
    errors[name]?.message ?? serverErrors[name]

  return (
    <form className="max-w-2xl space-y-4" noValidate onSubmit={form.handleSubmit(onSubmit)}>
      {error !== null && error !== undefined && (
        <Alert variant="destructive">
          <AlertDescription>{mutationErrorMessage(error)}</AlertDescription>
        </Alert>
      )}
      <div className="grid gap-4 sm:grid-cols-[10rem_1fr]">
        <Field label="Chave" htmlFor="key" error={fieldError('key')}>
          <Input
            id="key"
            disabled={isEdit}
            className="font-mono uppercase"
            aria-invalid={fieldError('key') ? true : undefined}
            {...form.register('key', { setValueAs: (value: string) => value.toUpperCase() })}
          />
        </Field>
        <Field label="Nome" htmlFor="name" error={fieldError('name')}>
          <Input
            id="name"
            aria-invalid={fieldError('name') ? true : undefined}
            {...form.register('name')}
          />
        </Field>
      </div>
      <Field label="Descrição" htmlFor="description" error={fieldError('description')}>
        <Textarea id="description" rows={4} {...form.register('description')} />
      </Field>
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Estado" htmlFor="status">
          <NativeSelect id="status" {...form.register('status')}>
            {(['active', 'on_hold', 'completed'] as const).map((value) => (
              <option key={value} value={value}>
                {projectStatusLabels[value]}
              </option>
            ))}
          </NativeSelect>
        </Field>
        <Field label="Prioridade" htmlFor="priority">
          <NativeSelect id="priority" {...form.register('priority')}>
            {(Object.keys(priorityLabels) as Priority[]).map((value) => (
              <option key={value} value={value}>
                {priorityLabels[value]}
              </option>
            ))}
          </NativeSelect>
        </Field>
        <Field label="Responsável" htmlFor="leadUserId" error={fieldError('leadUserId')}>
          <NativeSelect id="leadUserId" {...form.register('leadUserId')}>
            <option value="">{isEdit ? 'Sem responsável' : 'Eu próprio / nenhum'}</option>
            {project?.lead && !leads.some((lead) => lead.id === project.lead?.id) && (
              <option value={project.lead.id}>{project.lead.name}</option>
            )}
            {leads.map((lead) => (
              <option key={lead.id} value={lead.id}>
                {lead.name}
              </option>
            ))}
          </NativeSelect>
        </Field>
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Data de início" htmlFor="startDate" error={fieldError('startDate')}>
          <Input id="startDate" type="date" {...form.register('startDate')} />
        </Field>
        <Field label="Data alvo" htmlFor="targetDate" error={fieldError('targetDate')}>
          <Input
            id="targetDate"
            type="date"
            aria-invalid={fieldError('targetDate') ? true : undefined}
            {...form.register('targetDate')}
          />
        </Field>
        <Field
          label="Duração do sprint (dias)"
          htmlFor="sprintDurationDays"
          error={fieldError('sprintDurationDays')}
        >
          <Input
            id="sprintDurationDays"
            type="number"
            min={1}
            max={60}
            {...form.register('sprintDurationDays')}
          />
        </Field>
      </div>
      <div className="flex gap-2">
        <Button type="submit" disabled={submitting}>
          {submitting ? 'A guardar…' : isEdit ? 'Guardar alterações' : 'Criar projeto'}
        </Button>
        <Button variant="outline" asChild>
          <Link to={project ? `/projects/${project.id}` : '/projects'}>Cancelar</Link>
        </Button>
      </div>
    </form>
  )
}

function toPayload(values: ProjectFormValues) {
  return {
    name: values.name,
    description: values.description,
    status: values.status,
    priority: values.priority,
    leadUserId: values.leadUserId || null,
    startDate: values.startDate || null,
    targetDate: values.targetDate || null,
    settings: { sprintDurationDays: values.sprintDurationDays },
  }
}

export function ProjectCreatePage() {
  const navigate = useNavigate()
  const mutation = useCreateProject()
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Novo projeto</h1>
      <ProjectFormFields
        submitting={mutation.isPending}
        error={mutation.error}
        onSubmit={(values) =>
          mutation.mutate(
            { key: values.key, ...toPayload(values) },
            { onSuccess: (project) => void navigate(`/projects/${project.id}`) },
          )
        }
      />
    </div>
  )
}

export function ProjectEditPage() {
  const { projectId = '' } = useParams()
  const navigate = useNavigate()
  const project = useProject(projectId)
  const mutation = useUpdateProject(projectId)

  if (project.isPending) return <p className="text-muted-foreground">A carregar…</p>
  if (project.isError) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Projeto não encontrado ou sem acesso.</AlertDescription>
      </Alert>
    )
  }
  if (!project.data.canManage || project.data.status === 'archived') {
    return (
      <Alert>
        <AlertDescription>Não é possível editar este projeto.</AlertDescription>
      </Alert>
    )
  }
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Editar {project.data.name}</h1>
      <ProjectFormFields
        project={project.data}
        submitting={mutation.isPending}
        error={mutation.error}
        onSubmit={(values) => {
          const payload = toPayload(values)
          // Um Tech Lead não pode remover o responsável; omitir mantém o valor atual.
          const { leadUserId, ...rest } = payload
          mutation.mutate(
            {
              ...rest,
              ...(leadUserId !== null || project.data.lead === null ? { leadUserId } : {}),
              version: project.data.version,
            },
            { onSuccess: () => void navigate(`/projects/${projectId}`) },
          )
        }}
      />
    </div>
  )
}
