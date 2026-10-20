import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate, useParams } from 'react-router'
import { z } from 'zod'

import { Field } from '@/components/Field'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import { Textarea } from '@/components/ui/textarea'
import { useProjectContext } from '@/features/projects/projectContext'
import { useCreateRelease, useRelease, useUpdateRelease } from '@/features/releases/useReleases'
import { IssueLinks, TestPlanStatusBadge } from '@/features/testing/TestingShared'
import { useTestPlans } from '@/features/testing/useTesting'
import { usePermission } from '@/hooks/usePermissions'
import { mutationErrorMessage } from '@/lib/errors'
import { ApiError } from '@/services/apiClient'
import type { IssueRef } from '@/services/issues'
import {
  releaseCriteriaLabels,
  type Release,
  type ReleaseChecklistInput,
  type ReleaseCriteria,
  type ReleaseCriterionKey,
  type ReleaseInput,
  type TestPlanRef,
} from '@/services/releases'

const MAX_CHECKLIST = 30

const releaseSchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, 'Indique a versão')
    .max(40, 'Máximo 40 caracteres')
    .regex(/^[0-9A-Za-z._+-]+$/, 'Use apenas letras, números e . _ + - (ex.: 1.4.0)'),
  plannedDate: z.string(),
  description: z.string().max(5000, 'Máximo 5000 caracteres'),
  notes: z.string().max(20000, 'Máximo 20000 caracteres'),
})

type ReleaseFormValues = z.infer<typeof releaseSchema>
type ChecklistDraft = ReleaseChecklistInput & { key: string }

let draftCounter = 0
const draftKey = () => `item-${++draftCounter}`

function TestPlanPicker({
  projectId,
  value,
  onChange,
  readOnly,
  error,
}: {
  projectId: string
  value: TestPlanRef[]
  onChange: (plans: TestPlanRef[]) => void
  readOnly: boolean
  error?: string
}) {
  const candidates = useTestPlans({ projectId, pageSize: 100 })
  const selected = new Set(value.map((plan) => plan.id))
  const available = (candidates.data?.items ?? []).filter((plan) => !selected.has(plan.id))

  return (
    <div className="space-y-1.5">
      <Label htmlFor="release-test-plan">Planos de teste</Label>
      {value.length === 0 ? (
        <p className="text-sm text-muted-foreground">Nenhum plano de teste associado.</p>
      ) : (
        <ul className="space-y-1">
          {value.map((plan) => (
            <li key={plan.id} className="flex items-center gap-2 text-sm">
              <span>{plan.name}</span>
              <TestPlanStatusBadge status={plan.status} />
              {!readOnly && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  aria-label={`Remover ${plan.name}`}
                  onClick={() => onChange(value.filter((item) => item.id !== plan.id))}
                >
                  Remover
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
      {!readOnly && (
        <NativeSelect
          id="release-test-plan"
          value=""
          onChange={(event) => {
            const plan = available.find((item) => item.id === event.target.value)
            if (plan) onChange([...value, { id: plan.id, name: plan.name, status: plan.status }])
          }}
        >
          <option value="">Associar plano de teste…</option>
          {available.map((plan) => (
            <option key={plan.id} value={plan.id}>
              {plan.name}
            </option>
          ))}
        </NativeSelect>
      )}
      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  )
}

function ChecklistEditor({
  value,
  onChange,
  inherited,
  error,
}: {
  value: ChecklistDraft[]
  onChange: (items: ChecklistDraft[]) => void
  inherited: boolean
  error?: string
}) {
  const update = (key: string, changes: Partial<ChecklistDraft>) =>
    onChange(value.map((item) => (item.key === key ? { ...item, ...changes } : item)))

  return (
    <section aria-labelledby="release-checklist" className="space-y-2">
      <h3 id="release-checklist" className="font-medium">
        Checklist de aprovação
      </h3>
      {value.length === 0 && (
        <p className="text-sm text-muted-foreground">
          {inherited
            ? 'Sem itens: é usada a checklist da release anterior ou a checklist por omissão.'
            : 'Sem itens na checklist.'}
        </p>
      )}
      <ul className="space-y-2">
        {value.map((item, index) => (
          <li key={item.key} className="flex flex-wrap items-center gap-2">
            <Input
              className="max-w-md"
              aria-label={`Item ${index + 1} da checklist`}
              value={item.label}
              maxLength={200}
              onChange={(event) => update(item.key, { label: event.target.value })}
            />
            <label className="flex items-center gap-1 text-sm">
              <input
                type="checkbox"
                checked={item.required}
                onChange={(event) => update(item.key, { required: event.target.checked })}
              />
              Obrigatório
            </label>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              aria-label={`Remover item ${index + 1}`}
              onClick={() => onChange(value.filter((entry) => entry.key !== item.key))}
            >
              Remover
            </Button>
          </li>
        ))}
      </ul>
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={value.length >= MAX_CHECKLIST}
        onClick={() =>
          onChange([...value, { key: draftKey(), label: '', required: true, done: false }])
        }
      >
        Adicionar item
      </Button>
      {error && <p className="text-sm text-destructive">{error}</p>}
    </section>
  )
}

function ReleaseFormFields({
  release,
  submitting,
  error,
  onSubmit,
}: {
  release?: Release
  submitting: boolean
  error: unknown
  onSubmit: (input: ReleaseInput) => void
}) {
  const { project } = useProjectContext()
  const [issues, setIssues] = useState<IssueRef[]>(release?.issues ?? [])
  const [knownBugs, setKnownBugs] = useState<IssueRef[]>(release?.knownBugs ?? [])
  const [plans, setPlans] = useState<TestPlanRef[]>(release?.testPlans ?? [])
  const [checklist, setChecklist] = useState<ChecklistDraft[]>(
    (release?.checklist ?? []).map(({ id, label, required, done }) => ({
      key: id,
      id,
      label,
      required,
      done,
    })),
  )
  const [criteria, setCriteria] = useState<ReleaseCriteria>(
    release?.criteria ?? {
      issuesDone: true,
      testsPassed: true,
      noOpenCriticalBugs: true,
    },
  )
  const [checklistError, setChecklistError] = useState<string>()
  const form = useForm<ReleaseFormValues>({
    resolver: zodResolver(releaseSchema),
    defaultValues: {
      name: release?.name ?? '',
      plannedDate: release?.plannedDate ?? '',
      description: release?.description ?? '',
      notes: release?.notes ?? '',
    },
  })
  const { errors } = form.formState
  const serverErrors = error instanceof ApiError ? error.fieldErrors() : {}
  const fieldError = (name: keyof ReleaseFormValues) => errors[name]?.message ?? serverErrors[name]

  const submit = form.handleSubmit((values) => {
    if (checklist.some((item) => !item.label.trim())) {
      setChecklistError('Os itens da checklist precisam de descrição')
      return
    }
    setChecklistError(undefined)
    const items = checklist.map(({ id, label, required, done }) => ({
      ...(id ? { id } : {}),
      label: label.trim(),
      required,
      done,
    }))
    onSubmit({
      name: values.name,
      plannedDate: values.plannedDate || null,
      description: values.description,
      notes: values.notes,
      issueIds: issues.map((issue) => issue.id),
      knownBugIds: knownBugs.map((issue) => issue.id),
      testPlanIds: plans.map((plan) => plan.id),
      // Na criação, sem itens, o servidor herda a checklist da release anterior.
      ...(release || items.length > 0 ? { checklist: items } : {}),
      criteria,
    })
  })

  return (
    <form className="max-w-3xl space-y-4" noValidate onSubmit={submit}>
      {error !== null && error !== undefined && (
        <Alert variant="destructive">
          <AlertDescription>{mutationErrorMessage(error)}</AlertDescription>
        </Alert>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Versão" htmlFor="release-name" error={fieldError('name')}>
          <Input
            id="release-name"
            placeholder="1.4.0"
            aria-invalid={fieldError('name') ? true : undefined}
            {...form.register('name')}
          />
        </Field>
        <Field
          label="Data prevista"
          htmlFor="release-planned-date"
          error={fieldError('plannedDate')}
        >
          <Input id="release-planned-date" type="date" {...form.register('plannedDate')} />
        </Field>
      </div>
      <Field label="Descrição" htmlFor="release-description" error={fieldError('description')}>
        <Textarea id="release-description" rows={3} {...form.register('description')} />
      </Field>
      <Field
        label="Notas de release (markdown)"
        htmlFor="release-notes"
        error={fieldError('notes')}
      >
        <Textarea id="release-notes" rows={8} {...form.register('notes')} />
      </Field>
      <IssueLinks
        id="release-issues"
        label="Issues incluídas"
        emptyText="Nenhuma issue incluída."
        placeholder="Incluir issue…"
        projectId={project.id}
        value={issues}
        onChange={setIssues}
        readOnly={false}
        error={serverErrors.issueIds}
      />
      <IssueLinks
        id="release-known-bugs"
        label="Bugs conhecidos"
        emptyText="Nenhum bug conhecido."
        placeholder="Adicionar bug conhecido…"
        types={['bug']}
        projectId={project.id}
        value={knownBugs}
        onChange={setKnownBugs}
        readOnly={false}
        error={serverErrors.knownBugIds}
      />
      <TestPlanPicker
        projectId={project.id}
        value={plans}
        onChange={setPlans}
        readOnly={false}
        error={serverErrors.testPlanIds}
      />
      <ChecklistEditor
        value={checklist}
        onChange={setChecklist}
        inherited={!release}
        error={checklistError ?? serverErrors.checklist}
      />
      <fieldset className="space-y-2">
        <legend className="font-medium">Critérios de aprovação</legend>
        {(Object.keys(releaseCriteriaLabels) as ReleaseCriterionKey[]).map((key) => (
          <label key={key} className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={criteria[key]}
              onChange={(event) => setCriteria({ ...criteria, [key]: event.target.checked })}
            />
            {releaseCriteriaLabels[key]}
          </label>
        ))}
      </fieldset>
      <div className="flex gap-2">
        <Button type="submit" disabled={submitting}>
          {submitting ? 'A guardar…' : release ? 'Guardar alterações' : 'Criar release'}
        </Button>
        <Button variant="outline" asChild>
          <Link
            to={
              release
                ? `/projects/${project.id}/releases/${release.id}`
                : `/projects/${project.id}/releases`
            }
          >
            Cancelar
          </Link>
        </Button>
      </div>
    </form>
  )
}

export function ReleaseCreatePage() {
  const { project } = useProjectContext()
  const navigate = useNavigate()
  const canManage = usePermission('releases:manage')
  const mutation = useCreateRelease()

  if (!canManage || project.status === 'archived') {
    return (
      <Alert>
        <AlertDescription>Não é possível criar releases neste projeto.</AlertDescription>
      </Alert>
    )
  }

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">Nova release</h2>
      <ReleaseFormFields
        submitting={mutation.isPending}
        error={mutation.error}
        onSubmit={(input) =>
          mutation.mutate(
            { projectId: project.id, ...input },
            {
              onSuccess: (release) =>
                void navigate(`/projects/${project.id}/releases/${release.id}`),
            },
          )
        }
      />
    </div>
  )
}

export function ReleaseEditPage() {
  const { project } = useProjectContext()
  const { releaseId = '' } = useParams()
  const navigate = useNavigate()
  const release = useRelease(releaseId)
  const mutation = useUpdateRelease(releaseId)

  if (release.isPending) return <p className="text-muted-foreground">A carregar…</p>
  if (release.isError || release.data.projectId !== project.id) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Release não encontrada ou sem acesso.</AlertDescription>
      </Alert>
    )
  }
  const data = release.data
  if (!data.canEdit) {
    return (
      <Alert>
        <AlertDescription>
          Esta release não pode ser alterada.{' '}
          <Link to={`/projects/${project.id}/releases/${data.id}`}>Voltar</Link>
        </AlertDescription>
      </Alert>
    )
  }

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">Editar release {data.name}</h2>
      <ReleaseFormFields
        key={data.version}
        release={data}
        submitting={mutation.isPending}
        error={mutation.error}
        onSubmit={(input) =>
          mutation.mutate(
            { ...input, version: data.version },
            {
              onSuccess: () => void navigate(`/projects/${project.id}/releases/${data.id}`),
            },
          )
        }
      />
    </div>
  )
}
