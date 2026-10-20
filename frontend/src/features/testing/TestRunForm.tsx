import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'

import { Field } from '@/components/Field'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { NativeSelect } from '@/components/ui/native-select'
import { Textarea } from '@/components/ui/textarea'
import { useProjectContext } from '@/features/projects/projectContext'
import { useCreateTestRun, useTestCase, useTestPlan } from '@/features/testing/useTesting'
import { usePermission } from '@/hooks/usePermissions'
import { mutationErrorMessage } from '@/lib/errors'
import { ApiError } from '@/services/apiClient'
import { testRunResultLabels, type TestRunResult } from '@/services/testing'

/** Resultados escolhidos ao executar (`not_run` só aparece no progresso dos planos). */
const RUN_RESULTS: TestRunResult[] = ['pass', 'fail', 'blocked', 'skipped']
const TEXT_MAX = 5000

export function TestRunCreatePage() {
  const { project } = useProjectContext()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const testCaseId = params.get('testCaseId') ?? ''
  const testPlanId = params.get('testPlanId') ?? ''
  const canExecute = usePermission('tests:execute')
  const testCase = useTestCase(testCaseId)
  const plan = useTestPlan(testPlanId)
  const mutation = useCreateTestRun()
  const [result, setResult] = useState<TestRunResult>('pass')
  const [actualResult, setActualResult] = useState('')
  const [environment, setEnvironment] = useState('')
  const [notes, setNotes] = useState('')

  if (!canExecute || project.status === 'archived') {
    return (
      <Alert>
        <AlertDescription>Não é possível registar execuções neste projeto.</AlertDescription>
      </Alert>
    )
  }
  if (!testCaseId) {
    return (
      <Alert>
        <AlertDescription>Escolha o caso de teste a executar.</AlertDescription>
      </Alert>
    )
  }
  if (testCase.isPending) return <p className="text-muted-foreground">A carregar…</p>
  if (testCase.isError || testCase.data.projectId !== project.id) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Caso de teste não encontrado ou sem acesso.</AlertDescription>
      </Alert>
    )
  }

  const data = testCase.data
  const serverErrors = mutation.error instanceof ApiError ? mutation.error.fieldErrors() : {}
  const back = testPlanId
    ? `/projects/${project.id}/tests/plans/${testPlanId}`
    : `/projects/${project.id}/tests/cases/${data.id}`

  const submit = (event: FormEvent) => {
    event.preventDefault()
    mutation.mutate(
      {
        testCaseId: data.id,
        testPlanId: testPlanId || undefined,
        result,
        actualResult,
        environment,
        notes,
      },
      {
        onSuccess: (run) => void navigate(`/projects/${project.id}/tests/runs/${run.id}`),
      },
    )
  }

  return (
    <div className="max-w-3xl space-y-4">
      <h2 className="text-xl font-semibold">
        Executar {data.key} · {data.title}
      </h2>
      {testPlanId && plan.data && (
        <p className="text-sm text-muted-foreground">Plano: {plan.data.name}</p>
      )}
      <section className="space-y-2 rounded-lg border p-3 text-sm">
        {data.preconditions && (
          <p>
            <span className="font-medium">Pré-condições:</span> {data.preconditions}
          </p>
        )}
        <ol className="list-decimal space-y-1 pl-5">
          {data.steps.map((step, index) => (
            <li key={index}>
              {step.action}
              {step.expectedResult && (
                <span className="text-muted-foreground"> → {step.expectedResult}</span>
              )}
            </li>
          ))}
        </ol>
        {data.expectedResult && (
          <p>
            <span className="font-medium">Resultado esperado:</span> {data.expectedResult}
          </p>
        )}
      </section>

      <form className="space-y-4" noValidate onSubmit={submit}>
        {mutation.error !== null && (
          <Alert variant="destructive">
            <AlertDescription>{mutationErrorMessage(mutation.error)}</AlertDescription>
          </Alert>
        )}
        <Field label="Resultado" htmlFor="test-run-result-field" error={serverErrors.result}>
          <NativeSelect
            id="test-run-result-field"
            value={result}
            onChange={(event) => setResult(event.target.value as TestRunResult)}
          >
            {RUN_RESULTS.map((value) => (
              <option key={value} value={value}>
                {testRunResultLabels[value]}
              </option>
            ))}
          </NativeSelect>
        </Field>
        <Field label="Resultado obtido" htmlFor="test-run-actual" error={serverErrors.actualResult}>
          <Textarea
            id="test-run-actual"
            rows={3}
            maxLength={TEXT_MAX}
            value={actualResult}
            onChange={(event) => setActualResult(event.target.value)}
          />
        </Field>
        <Field label="Ambiente" htmlFor="test-run-environment" error={serverErrors.environment}>
          <Input
            id="test-run-environment"
            maxLength={200}
            placeholder="ex.: staging, Chrome 130"
            value={environment}
            onChange={(event) => setEnvironment(event.target.value)}
          />
        </Field>
        <Field label="Observações" htmlFor="test-run-notes" error={serverErrors.notes}>
          <Textarea
            id="test-run-notes"
            rows={3}
            maxLength={TEXT_MAX}
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
          />
        </Field>
        {(serverErrors.testCaseId || serverErrors.testPlanId) && (
          <p className="text-sm text-destructive">
            {serverErrors.testCaseId ?? serverErrors.testPlanId}
          </p>
        )}
        <div className="flex gap-2">
          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? 'A registar…' : 'Registar execução'}
          </Button>
          <Button variant="outline" asChild>
            <Link to={back}>Cancelar</Link>
          </Button>
        </div>
      </form>
    </div>
  )
}
