import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useFieldArray, useForm } from 'react-hook-form'
import { Link, useNavigate, useParams } from 'react-router'
import { z } from 'zod'

import { Field } from '@/components/Field'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { NativeSelect } from '@/components/ui/native-select'
import { Textarea } from '@/components/ui/textarea'
import { useProjectContext } from '@/features/projects/projectContext'
import { IssueLinks } from '@/features/testing/TestingShared'
import { useCreateTestCase, useTestCase, useUpdateTestCase } from '@/features/testing/useTesting'
import { usePermission } from '@/hooks/usePermissions'
import { mutationErrorMessage } from '@/lib/errors'
import { ApiError } from '@/services/apiClient'
import { priorityLabels, type Priority } from '@/services/common'
import type { IssueRef } from '@/services/issues'
import {
  testCaseStatusLabels,
  type TestCase,
  type TestCaseInput,
  type TestCaseStatus,
} from '@/services/testing'

const MAX_STEPS = 50

const testCaseSchema = z.object({
  title: z.string().trim().min(1, 'Indique o título').max(200, 'Máximo 200 caracteres'),
  description: z.string().max(5000, 'Máximo 5000 caracteres'),
  preconditions: z.string().max(5000, 'Máximo 5000 caracteres'),
  steps: z
    .array(
      z.object({
        action: z.string().trim().min(1, 'Indique a ação').max(1000, 'Máximo 1000 caracteres'),
        expectedResult: z.string().max(1000, 'Máximo 1000 caracteres'),
      }),
    )
    .min(1, 'Indique pelo menos um passo')
    .max(MAX_STEPS, `No máximo ${MAX_STEPS} passos`),
  expectedResult: z.string().max(2000, 'Máximo 2000 caracteres'),
  priority: z.enum(Object.keys(priorityLabels) as [Priority, ...Priority[]]),
  status: z.enum(Object.keys(testCaseStatusLabels) as [TestCaseStatus, ...TestCaseStatus[]]),
  labels: z.string(),
})

type TestCaseFormValues = z.infer<typeof testCaseSchema>

function parseLabels(value: string): string[] {
  return [...new Set(value.split(',').map((label) => label.trim().toLowerCase()).filter(Boolean))]
}

function TestCaseFormFields({
  testCase,
  readOnly,
  submitting,
  error,
  onSubmit,
}: {
  testCase?: TestCase
  readOnly: boolean
  submitting: boolean
  error: unknown
  onSubmit: (input: TestCaseInput) => void
}) {
  const { project } = useProjectContext()
  const [issues, setIssues] = useState<IssueRef[]>(testCase?.issues ?? [])
  const form = useForm<TestCaseFormValues>({
    resolver: zodResolver(testCaseSchema),
    defaultValues: {
      title: testCase?.title ?? '',
      description: testCase?.description ?? '',
      preconditions: testCase?.preconditions ?? '',
      steps: testCase?.steps ?? [{ action: '', expectedResult: '' }],
      expectedResult: testCase?.expectedResult ?? '',
      priority: testCase?.priority ?? 'medium',
      status: testCase?.status ?? 'draft',
      labels: testCase?.labels.join(', ') ?? '',
    },
  })
  const steps = useFieldArray({ control: form.control, name: 'steps' })
  const { errors } = form.formState
  const serverErrors = error instanceof ApiError ? error.fieldErrors() : {}
  const fieldError = (name: keyof TestCaseFormValues | 'issueIds') =>
    (name === 'issueIds' ? undefined : errors[name]?.message) ?? serverErrors[name]

  const submit = form.handleSubmit((values) =>
    onSubmit({
      ...values,
      steps: values.steps.map((step) => ({
        action: step.action.trim(),
        expectedResult: step.expectedResult.trim(),
      })),
      labels: parseLabels(values.labels),
      issueIds: issues.map((issue) => issue.id),
    }),
  )

  return (
    <form className="max-w-3xl space-y-4" noValidate onSubmit={submit}>
      {error !== null && error !== undefined && (
        <Alert variant="destructive">
          <AlertDescription>{mutationErrorMessage(error)}</AlertDescription>
        </Alert>
      )}
      <fieldset disabled={readOnly} className="space-y-4">
        <Field label="Título" htmlFor="test-case-title" error={fieldError('title')}>
          <Input
            id="test-case-title"
            aria-invalid={fieldError('title') ? true : undefined}
            {...form.register('title')}
          />
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Estado" htmlFor="test-case-status" error={fieldError('status')}>
            <NativeSelect id="test-case-status" {...form.register('status')}>
              {Object.entries(testCaseStatusLabels).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </NativeSelect>
          </Field>
          <Field label="Prioridade" htmlFor="test-case-priority" error={fieldError('priority')}>
            <NativeSelect id="test-case-priority" {...form.register('priority')}>
              {Object.entries(priorityLabels).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </NativeSelect>
          </Field>
        </div>
        <Field label="Descrição" htmlFor="test-case-description" error={fieldError('description')}>
          <Textarea id="test-case-description" rows={3} {...form.register('description')} />
        </Field>
        <Field
          label="Pré-condições"
          htmlFor="test-case-preconditions"
          error={fieldError('preconditions')}
        >
          <Textarea id="test-case-preconditions" rows={3} {...form.register('preconditions')} />
        </Field>

        <section aria-labelledby="test-case-steps" className="space-y-2">
          <h3 id="test-case-steps" className="font-medium">
            Passos
          </h3>
          <ol className="space-y-3">
            {steps.fields.map((step, index) => {
              const stepErrors = errors.steps?.[index]
              return (
                <li key={step.id} className="grid gap-2 rounded-md border p-3 sm:grid-cols-2">
                  <Field
                    label={`Ação do passo ${index + 1}`}
                    htmlFor={`step-${index}-action`}
                    error={stepErrors?.action?.message}
                  >
                    <Textarea
                      id={`step-${index}-action`}
                      rows={2}
                      {...form.register(`steps.${index}.action`)}
                    />
                  </Field>
                  <Field
                    label={`Resultado esperado do passo ${index + 1}`}
                    htmlFor={`step-${index}-expected`}
                    error={stepErrors?.expectedResult?.message}
                  >
                    <Textarea
                      id={`step-${index}-expected`}
                      rows={2}
                      {...form.register(`steps.${index}.expectedResult`)}
                    />
                  </Field>
                  {!readOnly && (
                    <div className="flex gap-2 sm:col-span-2">
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        disabled={index === 0}
                        onClick={() => steps.move(index, index - 1)}
                      >
                        Subir
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        disabled={steps.fields.length === 1}
                        aria-label={`Remover passo ${index + 1}`}
                        onClick={() => steps.remove(index)}
                      >
                        Remover
                      </Button>
                    </div>
                  )}
                </li>
              )
            })}
          </ol>
          {(errors.steps?.root?.message ?? errors.steps?.message ?? serverErrors.steps) && (
            <p className="text-sm text-destructive">
              {errors.steps?.root?.message ?? errors.steps?.message ?? serverErrors.steps}
            </p>
          )}
          {!readOnly && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={steps.fields.length >= MAX_STEPS}
              onClick={() => steps.append({ action: '', expectedResult: '' })}
            >
              Adicionar passo
            </Button>
          )}
        </section>

        <Field
          label="Resultado esperado"
          htmlFor="test-case-expected"
          error={fieldError('expectedResult')}
        >
          <Textarea id="test-case-expected" rows={2} {...form.register('expectedResult')} />
        </Field>
        <Field label="Labels" htmlFor="test-case-labels" error={fieldError('labels')}>
          <Input
            id="test-case-labels"
            placeholder="Separadas por vírgulas"
            {...form.register('labels')}
          />
        </Field>
      </fieldset>
      <IssueLinks
        projectId={project.id}
        value={issues}
        onChange={setIssues}
        readOnly={readOnly}
        error={fieldError('issueIds')}
      />
      <div className="flex gap-2">
        {!readOnly && (
          <Button type="submit" disabled={submitting}>
            {submitting ? 'A guardar…' : testCase ? 'Guardar alterações' : 'Criar caso de teste'}
          </Button>
        )}
        <Button variant="outline" asChild>
          <Link to={`/projects/${project.id}/tests`}>{readOnly ? 'Voltar' : 'Cancelar'}</Link>
        </Button>
      </div>
    </form>
  )
}

export function TestCaseCreatePage() {
  const { project } = useProjectContext()
  const navigate = useNavigate()
  const canManage = usePermission('tests:manage')
  const mutation = useCreateTestCase()

  if (!canManage || project.status === 'archived') {
    return (
      <Alert>
        <AlertDescription>Não é possível criar casos de teste neste projeto.</AlertDescription>
      </Alert>
    )
  }

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">Novo caso de teste</h2>
      <TestCaseFormFields
        readOnly={false}
        submitting={mutation.isPending}
        error={mutation.error}
        onSubmit={(input) =>
          mutation.mutate(
            { projectId: project.id, ...input },
            { onSuccess: () => void navigate(`/projects/${project.id}/tests`) },
          )
        }
      />
    </div>
  )
}

export function TestCaseEditPage() {
  const { project } = useProjectContext()
  const { testCaseId = '' } = useParams()
  const navigate = useNavigate()
  const testCase = useTestCase(testCaseId)
  const mutation = useUpdateTestCase(testCaseId)

  if (testCase.isPending) return <p className="text-muted-foreground">A carregar…</p>
  if (testCase.isError || testCase.data.projectId !== project.id) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Caso de teste não encontrado ou sem acesso.</AlertDescription>
      </Alert>
    )
  }

  const data = testCase.data
  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">
        {data.key} · {data.title}
      </h2>
      {!data.canEdit && (
        <p className="text-sm text-muted-foreground">Consulta apenas: sem permissão para editar.</p>
      )}
      <TestCaseFormFields
        key={data.version}
        testCase={data}
        readOnly={!data.canEdit}
        submitting={mutation.isPending}
        error={mutation.error}
        onSubmit={(input) =>
          mutation.mutate(
            { ...input, version: data.version },
            { onSuccess: () => void navigate(`/projects/${project.id}/tests`) },
          )
        }
      />
    </div>
  )
}

