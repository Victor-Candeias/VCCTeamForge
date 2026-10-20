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
import { IssueLinks, TestCaseStatusBadge } from '@/features/testing/TestingShared'
import { useCreateTestPlan, useTestCases, useTestPlan, useUpdateTestPlan } from '@/features/testing/useTesting'
import { usePermission } from '@/hooks/usePermissions'
import { mutationErrorMessage } from '@/lib/errors'
import { ApiError } from '@/services/apiClient'
import type { IssueRef } from '@/services/issues'
import {
  testPlanStatusLabels,
  type TestCaseRef,
  type TestPlan,
  type TestPlanInput,
  type TestPlanStatus,
} from '@/services/testing'

const MAX_CASES = 500

const testPlanSchema = z.object({
  name: z.string().trim().min(1, 'Indique o nome').max(120, 'Máximo 120 caracteres'),
  description: z.string().max(5000, 'Máximo 5000 caracteres'),
  status: z.enum(Object.keys(testPlanStatusLabels) as [TestPlanStatus, ...TestPlanStatus[]]),
})

type TestPlanFormValues = z.infer<typeof testPlanSchema>

function move<T>(items: T[], from: number, to: number): T[] {
  const result = [...items]
  const [item] = result.splice(from, 1)
  result.splice(to, 0, item)
  return result
}

function TestCasePicker({
  projectId,
  value,
  onChange,
  readOnly,
  error,
}: {
  projectId: string
  value: TestCaseRef[]
  onChange: (cases: TestCaseRef[]) => void
  readOnly: boolean
  error?: string
}) {
  // Só casos ativos podem entrar no plano; os obsoletos já incluídos mantêm-se.
  const candidates = useTestCases(
    { projectId, status: ['draft', 'ready'], pageSize: 100 },
    !readOnly,
  )
  const selected = new Set(value.map((testCase) => testCase.id))
  const available = (candidates.data?.items ?? []).filter((testCase) => !selected.has(testCase.id))

  return (
    <section aria-labelledby="plan-cases" className="space-y-2">
      <h3 id="plan-cases" className="font-medium">
        Casos de teste ({value.length})
      </h3>
      {value.length === 0 ? (
        <p className="text-sm text-muted-foreground">Nenhum caso no plano.</p>
      ) : (
        <ol className="space-y-1">
          {value.map((testCase, index) => (
            <li key={testCase.id} className="flex flex-wrap items-center gap-2 text-sm">
              <span className="font-mono text-xs">{testCase.key}</span>
              <Link
                className="hover:underline"
                to={`/projects/${projectId}/tests/cases/${testCase.id}`}
              >
                {testCase.title}
              </Link>
              <TestCaseStatusBadge status={testCase.status} />
              {!readOnly && (
                <>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    disabled={index === 0}
                    aria-label={`Subir ${testCase.key}`}
                    onClick={() => onChange(move(value, index, index - 1))}
                  >
                    Subir
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    aria-label={`Remover ${testCase.key}`}
                    onClick={() => onChange(value.filter((item) => item.id !== testCase.id))}
                  >
                    Remover
                  </Button>
                </>
              )}
            </li>
          ))}
        </ol>
      )}
      {!readOnly && (
        <div className="space-y-1.5">
          <Label htmlFor="add-test-case">Adicionar caso</Label>
          <NativeSelect
            id="add-test-case"
            value=""
            disabled={value.length >= MAX_CASES}
            onChange={(event) => {
              const testCase = available.find((item) => item.id === event.target.value)
              if (testCase) onChange([...value, testCase])
            }}
          >
            <option value="">Escolher caso de teste…</option>
            {available.map((testCase) => (
              <option key={testCase.id} value={testCase.id}>
                {testCase.key} · {testCase.title}
              </option>
            ))}
          </NativeSelect>
        </div>
      )}
      {error && <p className="text-sm text-destructive">{error}</p>}
    </section>
  )
}

function TestPlanFormFields({
  plan,
  readOnly,
  submitting,
  error,
  onSubmit,
}: {
  plan?: TestPlan
  readOnly: boolean
  submitting: boolean
  error: unknown
  onSubmit: (input: TestPlanInput) => void
}) {
  const { project } = useProjectContext()
  const [cases, setCases] = useState<TestCaseRef[]>(plan?.testCases ?? [])
  const [issues, setIssues] = useState<IssueRef[]>(plan?.issues ?? [])
  const form = useForm<TestPlanFormValues>({
    resolver: zodResolver(testPlanSchema),
    defaultValues: {
      name: plan?.name ?? '',
      description: plan?.description ?? '',
      status: plan?.status ?? 'draft',
    },
  })
  const { errors } = form.formState
  const serverErrors = error instanceof ApiError ? error.fieldErrors() : {}
  const fieldError = (name: keyof TestPlanFormValues) =>
    errors[name]?.message ?? serverErrors[name]
  // Um plano fechado só pode ser reaberto: o resto fica só de leitura.
  const closed = plan?.status === 'closed'
  const contentReadOnly = readOnly || closed

  const submit = form.handleSubmit((values) =>
    onSubmit({
      ...values,
      testCaseIds: cases.map((testCase) => testCase.id),
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
      {closed && !readOnly && (
        <p className="text-sm text-muted-foreground">
          O plano está fechado: mude o estado para o reabrir antes de o alterar.
        </p>
      )}
      <fieldset disabled={readOnly} className="space-y-4">
        <Field label="Nome" htmlFor="test-plan-name" error={fieldError('name')}>
          <Input
            id="test-plan-name"
            readOnly={contentReadOnly}
            aria-invalid={fieldError('name') ? true : undefined}
            {...form.register('name')}
          />
        </Field>
        <Field label="Estado" htmlFor="test-plan-status-field" error={fieldError('status')}>
          <NativeSelect id="test-plan-status-field" {...form.register('status')}>
            {Object.entries(testPlanStatusLabels).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </NativeSelect>
        </Field>
        <Field label="Descrição" htmlFor="test-plan-description" error={fieldError('description')}>
          <Textarea
            id="test-plan-description"
            rows={3}
            readOnly={contentReadOnly}
            {...form.register('description')}
          />
        </Field>
      </fieldset>
      <TestCasePicker
        projectId={project.id}
        value={cases}
        onChange={setCases}
        readOnly={contentReadOnly}
        error={serverErrors.testCaseIds}
      />
      <IssueLinks
        projectId={project.id}
        value={issues}
        onChange={setIssues}
        readOnly={contentReadOnly}
        error={serverErrors.issueIds}
      />
      <div className="flex gap-2">
        {!readOnly && (
          <Button type="submit" disabled={submitting}>
            {submitting ? 'A guardar…' : plan ? 'Guardar alterações' : 'Criar plano de teste'}
          </Button>
        )}
        <Button variant="outline" asChild>
          <Link to={`/projects/${project.id}/tests/plans`}>{readOnly ? 'Voltar' : 'Cancelar'}</Link>
        </Button>
      </div>
    </form>
  )
}

export function TestPlanCreatePage() {
  const { project } = useProjectContext()
  const navigate = useNavigate()
  const canManage = usePermission('tests:manage')
  const mutation = useCreateTestPlan()

  if (!canManage || project.status === 'archived') {
    return (
      <Alert>
        <AlertDescription>Não é possível criar planos de teste neste projeto.</AlertDescription>
      </Alert>
    )
  }

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">Novo plano de teste</h2>
      <TestPlanFormFields
        readOnly={false}
        submitting={mutation.isPending}
        error={mutation.error}
        onSubmit={(input) =>
          mutation.mutate(
            { projectId: project.id, ...input },
            { onSuccess: () => void navigate(`/projects/${project.id}/tests/plans`) },
          )
        }
      />
    </div>
  )
}

export function TestPlanEditPage() {
  const { project } = useProjectContext()
  const { testPlanId = '' } = useParams()
  const navigate = useNavigate()
  const plan = useTestPlan(testPlanId)
  const mutation = useUpdateTestPlan(testPlanId)

  if (plan.isPending) return <p className="text-muted-foreground">A carregar…</p>
  if (plan.isError || plan.data.projectId !== project.id) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Plano de teste não encontrado ou sem acesso.</AlertDescription>
      </Alert>
    )
  }

  const data = plan.data
  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">{data.name}</h2>
      {!data.canEdit && (
        <p className="text-sm text-muted-foreground">Consulta apenas: sem permissão para editar.</p>
      )}
      <TestPlanFormFields
        key={data.version}
        plan={data}
        readOnly={!data.canEdit}
        submitting={mutation.isPending}
        error={mutation.error}
        onSubmit={(input) =>
          mutation.mutate(
            data.status === 'closed'
              ? { status: input.status, version: data.version }
              : { ...input, version: data.version },
            { onSuccess: () => void navigate(`/projects/${project.id}/tests/plans`) },
          )
        }
      />
    </div>
  )
}
