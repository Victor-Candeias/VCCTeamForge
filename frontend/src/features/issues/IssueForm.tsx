import { zodResolver } from '@hookform/resolvers/zod'
import { useForm, useWatch } from 'react-hook-form'
import { Link, useNavigate, useParams } from 'react-router'
import { z } from 'zod'

import { Field } from '@/components/Field'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { NativeSelect } from '@/components/ui/native-select'
import { Textarea } from '@/components/ui/textarea'
import { useCurrentUser } from '@/features/auth/useAuth'
import { useCreateIssue, useIssue, useIssues, useUpdateIssue } from '@/features/issues/useIssues'
import { useProjectContext } from '@/features/projects/projectContext'
import { useProject, useProjectMembers } from '@/features/projects/useProjects'
import { mutationErrorMessage } from '@/lib/errors'
import { ApiError } from '@/services/apiClient'
import { priorityLabels, type Priority } from '@/services/common'
import {
  canBeParent,
  issueTypeLabels,
  issueTypes,
  type Issue,
  type IssueFields,
  type IssueType,
} from '@/services/issues'
import type { Project } from '@/services/projects'

function isValidStoryPoints(value: string) {
  if (value === '') return true
  const points = Number(value.replace(',', '.'))
  return points >= 0 && points <= 100 && Number.isInteger(points * 2)
}

const issueSchema = z
  .object({
    type: z.enum(issueTypes as [IssueType, ...IssueType[]]),
    title: z.string().trim().min(1, 'Indique o título').max(200, 'Máximo 200 caracteres'),
    description: z.string().max(20000, 'Máximo 20 000 caracteres'),
    priority: z.enum(['low', 'medium', 'high', 'critical']),
    assigneeId: z.string(),
    parentIssueId: z.string(),
    storyPoints: z
      .string()
      .trim()
      .refine(isValidStoryPoints, 'Entre 0 e 100, em múltiplos de 0,5'),
    labels: z.string().refine(
      (value) => splitLabels(value).every((label) => label.length <= 40),
      'Cada label tem no máximo 40 caracteres',
    ),
    acceptanceCriteria: z.string(),
    dueDate: z.union([z.literal(''), z.iso.date('Data inválida')]),
  })
  .refine((data) => data.type !== 'subtask' || data.parentIssueId !== '', {
    message: 'Uma subtarefa tem de ter uma issue pai',
    path: ['parentIssueId'],
  })

type IssueFormValues = z.infer<typeof issueSchema>

function splitLabels(value: string) {
  return value
    .split(',')
    .map((label) => label.trim().toLowerCase())
    .filter(Boolean)
}

function defaultsFrom(issue?: Issue): IssueFormValues {
  return {
    type: issue?.type ?? 'story',
    title: issue?.title ?? '',
    description: issue?.description ?? '',
    priority: issue?.priority ?? 'medium',
    assigneeId: issue?.assignee?.id ?? '',
    parentIssueId: issue?.parent?.id ?? '',
    storyPoints: issue?.storyPoints === null || issue === undefined ? '' : String(issue.storyPoints),
    labels: issue?.labels.join(', ') ?? '',
    acceptanceCriteria: issue?.acceptanceCriteria.join('\n') ?? '',
    dueDate: issue?.dueDate ?? '',
  }
}

function toFields(values: IssueFormValues): IssueFields {
  return {
    title: values.title,
    description: values.description,
    priority: values.priority as Priority,
    assigneeId: values.assigneeId || null,
    parentIssueId: values.parentIssueId || null,
    storyPoints: values.storyPoints === '' ? null : Number(values.storyPoints.replace(',', '.')),
    labels: splitLabels(values.labels),
    acceptanceCriteria: values.acceptanceCriteria
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean),
    dueDate: values.dueDate || null,
  }
}

function IssueFormFields({
  project,
  issue,
  submitting,
  error,
  onSubmit,
}: {
  project: Project
  issue?: Issue
  submitting: boolean
  error: unknown
  onSubmit: (values: IssueFormValues) => void
}) {
  const { data: user } = useCurrentUser()
  const form = useForm<IssueFormValues>({
    resolver: zodResolver(issueSchema),
    defaultValues: defaultsFrom(issue),
  })
  const members = useProjectMembers(project.id)
  const candidates = useIssues({ projectId: project.id, pageSize: 100 })
  const type = useWatch({ control: form.control, name: 'type' })
  const parents = (candidates.data?.items ?? []).filter(
    (candidate) => candidate.id !== issue?.id && canBeParent(type, candidate),
  )
  const allowedTypes = user?.role === 'qa' ? (['bug'] as IssueType[]) : issueTypes
  const { errors } = form.formState
  const serverErrors = error instanceof ApiError ? error.fieldErrors() : {}
  const fieldError = (name: keyof IssueFormValues) => errors[name]?.message ?? serverErrors[name]

  return (
    <form className="max-w-3xl space-y-4" noValidate onSubmit={form.handleSubmit(onSubmit)}>
      {error !== null && error !== undefined && (
        <Alert variant="destructive">
          <AlertDescription>{mutationErrorMessage(error)}</AlertDescription>
        </Alert>
      )}
      <div className="grid gap-4 sm:grid-cols-[12rem_1fr]">
        <Field label="Tipo" htmlFor="type">
          <NativeSelect id="type" disabled={Boolean(issue)} {...form.register('type')}>
            {(issue ? [issue.type] : allowedTypes).map((value) => (
              <option key={value} value={value}>
                {issueTypeLabels[value]}
              </option>
            ))}
          </NativeSelect>
        </Field>
        <Field label="Título" htmlFor="title" error={fieldError('title')}>
          <Input
            id="title"
            aria-invalid={fieldError('title') ? true : undefined}
            {...form.register('title')}
          />
        </Field>
      </div>
      <Field label="Descrição (Markdown)" htmlFor="description" error={fieldError('description')}>
        <Textarea id="description" rows={8} {...form.register('description')} />
      </Field>
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Prioridade" htmlFor="priority">
          <NativeSelect id="priority" {...form.register('priority')}>
            {(Object.keys(priorityLabels) as Priority[]).map((value) => (
              <option key={value} value={value}>
                {priorityLabels[value]}
              </option>
            ))}
          </NativeSelect>
        </Field>
        <Field label="Responsável" htmlFor="assigneeId" error={fieldError('assigneeId')}>
          <NativeSelect id="assigneeId" {...form.register('assigneeId')}>
            <option value="">Sem responsável</option>
            {(members.data?.members ?? []).map((member) => (
              <option key={member.id} value={member.id}>
                {member.name}
              </option>
            ))}
          </NativeSelect>
        </Field>
        <Field label="Story points" htmlFor="storyPoints" error={fieldError('storyPoints')}>
          <Input id="storyPoints" inputMode="decimal" {...form.register('storyPoints')} />
        </Field>
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Issue pai" htmlFor="parentIssueId" error={fieldError('parentIssueId')}>
          <NativeSelect
            id="parentIssueId"
            disabled={type === 'epic'}
            {...form.register('parentIssueId')}
          >
            <option value="">Nenhuma</option>
            {issue?.parent && !parents.some((parent) => parent.id === issue.parent?.id) && (
              <option value={issue.parent.id}>
                {issue.parent.key} · {issue.parent.title}
              </option>
            )}
            {parents.map((parent) => (
              <option key={parent.id} value={parent.id}>
                {parent.key} · {parent.title}
              </option>
            ))}
          </NativeSelect>
        </Field>
        <Field label="Labels (separadas por vírgula)" htmlFor="labels" error={fieldError('labels')}>
          <Input id="labels" {...form.register('labels')} />
        </Field>
        <Field label="Data limite" htmlFor="dueDate" error={fieldError('dueDate')}>
          <Input id="dueDate" type="date" {...form.register('dueDate')} />
        </Field>
      </div>
      <Field
        label="Critérios de aceitação (um por linha)"
        htmlFor="acceptanceCriteria"
        error={fieldError('acceptanceCriteria')}
      >
        <Textarea id="acceptanceCriteria" rows={4} {...form.register('acceptanceCriteria')} />
      </Field>
      <div className="flex gap-2">
        <Button type="submit" disabled={submitting}>
          {submitting ? 'A guardar…' : issue ? 'Guardar alterações' : 'Criar issue'}
        </Button>
        <Button variant="outline" asChild>
          <Link to={issue ? `/issues/${issue.key}` : `/projects/${project.id}/issues`}>
            Cancelar
          </Link>
        </Button>
      </div>
    </form>
  )
}

export function IssueCreatePage() {
  const { project } = useProjectContext()
  const navigate = useNavigate()
  const mutation = useCreateIssue()
  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">Nova issue</h2>
      <IssueFormFields
        project={project}
        submitting={mutation.isPending}
        error={mutation.error}
        onSubmit={(values) =>
          mutation.mutate(
            { projectId: project.id, type: values.type, ...toFields(values) },
            { onSuccess: (issue) => void navigate(`/issues/${issue.key}`) },
          )
        }
      />
    </div>
  )
}

export function IssueEditPage() {
  const { issueKey = '' } = useParams()
  const navigate = useNavigate()
  const issue = useIssue(issueKey)
  const project = useProject(issue.data?.projectId ?? '')
  const mutation = useUpdateIssue(issue.data?.id ?? '')

  if (issue.isError || project.isError) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Issue não encontrada ou sem acesso.</AlertDescription>
      </Alert>
    )
  }
  if (!issue.data || !project.data) return <p className="text-muted-foreground">A carregar…</p>
  if (!issue.data.canEdit) {
    return (
      <Alert>
        <AlertDescription>Não pode editar esta issue.</AlertDescription>
      </Alert>
    )
  }
  const current = issue.data
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Editar {current.key}</h1>
      <IssueFormFields
        project={project.data}
        issue={current}
        submitting={mutation.isPending}
        error={mutation.error}
        onSubmit={(values) =>
          mutation.mutate(
            { ...toFields(values), version: current.version },
            { onSuccess: (updated) => void navigate(`/issues/${updated.key}`) },
          )
        }
      />
    </div>
  )
}
