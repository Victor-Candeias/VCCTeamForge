import { useRef, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router'

import { Field } from '@/components/Field'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import { Textarea } from '@/components/ui/textarea'
import { IssueStatusBadge } from '@/features/issues/IssueBadges'
import { useProjectContext } from '@/features/projects/projectContext'
import { TestRunResultBadge } from '@/features/testing/TestingShared'
import {
  useCreateTestRunBug,
  useTestRun,
  useTestRunEvidenceMutations,
  useTestRunEvidences,
  useUpdateTestRun,
} from '@/features/testing/useTesting'
import { mutationErrorMessage } from '@/lib/errors'
import { ApiError } from '@/services/apiClient'
import {
  ATTACHMENT_EXTENSIONS,
  ATTACHMENT_MAX_BYTES,
  formatFileSize,
} from '@/services/attachments'
import { formatDateTime } from '@/services/common'
import {
  testRunEvidenceUrl,
  testRunResultLabels,
  type TestRun,
  type TestRunEvidence,
  type TestRunResult,
} from '@/services/testing'

const RUN_RESULTS: TestRunResult[] = ['pass', 'fail', 'blocked', 'skipped']
const accept = ATTACHMENT_EXTENSIONS.map((extension) => `.${extension}`).join(',')

function TestRunEditForm({ run }: { run: TestRun }) {
  const mutation = useUpdateTestRun(run.id)
  const [result, setResult] = useState<TestRunResult>(run.result)
  const [actualResult, setActualResult] = useState(run.actualResult)
  const [environment, setEnvironment] = useState(run.environment)
  const [notes, setNotes] = useState(run.notes)
  const serverErrors = mutation.error instanceof ApiError ? mutation.error.fieldErrors() : {}
  const readOnly = !run.canEdit

  const submit = (event: FormEvent) => {
    event.preventDefault()
    mutation.mutate({ result, actualResult, environment, notes, version: run.version })
  }

  return (
    <form className="space-y-4" noValidate onSubmit={submit}>
      {mutation.error !== null && (
        <Alert variant="destructive">
          <AlertDescription>{mutationErrorMessage(mutation.error)}</AlertDescription>
        </Alert>
      )}
      {mutation.isSuccess && <p className="text-sm text-muted-foreground">Alterações guardadas.</p>}
      <fieldset disabled={readOnly} className="space-y-4">
        <Field label="Resultado" htmlFor="test-run-result-field" error={serverErrors.result}>
          <NativeSelect
            id="test-run-result-field"
            value={result}
            onChange={(event) => setResult(event.target.value as TestRunResult)}
          >
            {(RUN_RESULTS.includes(run.result) ? RUN_RESULTS : [run.result, ...RUN_RESULTS]).map(
              (value) => (
                <option key={value} value={value}>
                  {testRunResultLabels[value]}
                </option>
              ),
            )}
          </NativeSelect>
        </Field>
        <Field label="Resultado obtido" htmlFor="test-run-actual" error={serverErrors.actualResult}>
          <Textarea
            id="test-run-actual"
            rows={3}
            maxLength={5000}
            value={actualResult}
            onChange={(event) => setActualResult(event.target.value)}
          />
        </Field>
        <Field label="Ambiente" htmlFor="test-run-environment" error={serverErrors.environment}>
          <Input
            id="test-run-environment"
            maxLength={200}
            value={environment}
            onChange={(event) => setEnvironment(event.target.value)}
          />
        </Field>
        <Field label="Observações" htmlFor="test-run-notes" error={serverErrors.notes}>
          <Textarea
            id="test-run-notes"
            rows={3}
            maxLength={5000}
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
          />
        </Field>
      </fieldset>
      {!readOnly && (
        <Button type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? 'A guardar…' : 'Guardar alterações'}
        </Button>
      )}
    </form>
  )
}

function TestRunBugs({ run }: { run: TestRun }) {
  const mutation = useCreateTestRunBug(run.id)
  const [title, setTitle] = useState('')
  return (
    <section className="space-y-2">
      <h3 className="font-medium">Bugs ligados</h3>
      {run.bugs.length === 0 ? (
        <p className="text-sm text-muted-foreground">Nenhum bug ligado.</p>
      ) : (
        <ul className="space-y-1">
          {run.bugs.map((bug) => (
            <li key={bug.id} className="flex items-center gap-2 text-sm">
              <Link className="hover:underline" to={`/issues/${bug.key}`}>
                {bug.key} · {bug.title}
              </Link>
              <IssueStatusBadge status={bug.status} />
            </li>
          ))}
        </ul>
      )}
      {mutation.error !== null && (
        <Alert variant="destructive">
          <AlertDescription>{mutationErrorMessage(mutation.error)}</AlertDescription>
        </Alert>
      )}
      {run.canCreateBug && (
        <form
          className="flex flex-wrap items-end gap-2"
          onSubmit={(event) => {
            event.preventDefault()
            mutation.mutate(
              { title: title.trim() || undefined },
              { onSuccess: () => setTitle('') },
            )
          }}
        >
          <div className="min-w-64 flex-1 space-y-1">
            <Label htmlFor="test-run-bug-title">Título do bug (opcional)</Label>
            <Input
              id="test-run-bug-title"
              maxLength={200}
              placeholder={`Falha em ${run.testCaseKey}: ${run.testCaseTitle}`}
              value={title}
              onChange={(event) => setTitle(event.target.value)}
            />
          </div>
          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? 'A criar…' : 'Criar bug'}
          </Button>
        </form>
      )}
    </section>
  )
}

function EvidenceRow({
  runId,
  evidence,
  onRemove,
  removing,
}: {
  runId: string
  evidence: TestRunEvidence
  onRemove: () => void
  removing: boolean
}) {
  const [confirming, setConfirming] = useState(false)
  return (
    <li className="flex flex-wrap items-center gap-3 rounded-lg border p-2 text-sm">
      {evidence.isImage && (
        <img
          src={testRunEvidenceUrl(runId, evidence.id, true)}
          alt=""
          className="size-10 rounded object-cover"
          loading="lazy"
        />
      )}
      <div className="min-w-0 flex-1">
        <a
          className="font-medium hover:underline"
          href={testRunEvidenceUrl(runId, evidence.id)}
          download
        >
          {evidence.originalName}
        </a>
        <div className="text-muted-foreground">
          {formatFileSize(evidence.size)} · {evidence.uploadedBy?.name ?? 'Utilizador removido'} ·{' '}
          {formatDateTime(evidence.createdAt)}
        </div>
      </div>
      {evidence.canDelete &&
        (confirming ? (
          <div className="flex gap-2">
            <Button size="sm" variant="destructive" disabled={removing} onClick={onRemove}>
              Confirmar remoção
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setConfirming(false)}>
              Cancelar
            </Button>
          </div>
        ) : (
          <Button
            size="sm"
            variant="ghost"
            aria-label={`Remover ${evidence.originalName}`}
            onClick={() => setConfirming(true)}
          >
            Remover
          </Button>
        ))}
    </li>
  )
}

function TestRunEvidences({ run }: { run: TestRun }) {
  const evidences = useTestRunEvidences(run.id)
  const { upload, remove } = useTestRunEvidenceMutations(run.id)
  const [clientError, setClientError] = useState<string | null>(null)
  const input = useRef<HTMLInputElement>(null)
  const mutationError = upload.error ?? remove.error
  const error = clientError ?? (mutationError ? mutationErrorMessage(mutationError) : null)

  const onFile = (file: File | undefined) => {
    upload.reset()
    remove.reset()
    setClientError(null)
    if (!file) return
    if (file.size > ATTACHMENT_MAX_BYTES) {
      setClientError(`O ficheiro excede o máximo de ${formatFileSize(ATTACHMENT_MAX_BYTES)}.`)
    } else {
      upload.mutate(file)
    }
    if (input.current) input.current.value = ''
  }

  return (
    <section className="space-y-2">
      <h3 className="font-medium">Evidências</h3>
      {evidences.isError && (
        <Alert variant="destructive">
          <AlertDescription>Não foi possível carregar as evidências.</AlertDescription>
        </Alert>
      )}
      {evidences.data && evidences.data.length === 0 && (
        <p className="text-sm text-muted-foreground">Sem evidências.</p>
      )}
      {evidences.data && evidences.data.length > 0 && (
        <ul className="space-y-2">
          {evidences.data.map((evidence) => (
            <EvidenceRow
              key={evidence.id}
              runId={run.id}
              evidence={evidence}
              removing={remove.isPending}
              onRemove={() => remove.mutate(evidence.id)}
            />
          ))}
        </ul>
      )}
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {run.canAddEvidence && (
        <div className="space-y-1">
          <Label htmlFor="evidence-file">Adicionar evidência</Label>
          <input
            ref={input}
            id="evidence-file"
            type="file"
            accept={accept}
            disabled={upload.isPending}
            className="block text-sm file:mr-3 file:rounded-md file:border file:bg-background file:px-3 file:py-1"
            onChange={(event) => onFile(event.target.files?.[0])}
          />
          <p className="text-xs text-muted-foreground">
            {upload.isPending
              ? 'A carregar…'
              : `Máximo ${formatFileSize(ATTACHMENT_MAX_BYTES)}; tipos: ${ATTACHMENT_EXTENSIONS.join(', ')}.`}
          </p>
        </div>
      )}
    </section>
  )
}

export function TestRunDetailPage() {
  const { project } = useProjectContext()
  const { testRunId = '' } = useParams()
  const run = useTestRun(testRunId)

  if (run.isPending) return <p className="text-muted-foreground">A carregar…</p>
  if (run.isError || run.data.projectId !== project.id) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Execução não encontrada ou sem acesso.</AlertDescription>
      </Alert>
    )
  }

  const data = run.data
  return (
    <div className="max-w-3xl space-y-6">
      <div className="space-y-1">
        <h2 className="flex flex-wrap items-center gap-2 text-xl font-semibold">
          <Link
            className="hover:underline"
            to={`/projects/${project.id}/tests/cases/${data.testCaseId}`}
          >
            {data.testCaseKey} · {data.testCaseTitle}
          </Link>
          <TestRunResultBadge result={data.result} />
        </h2>
        <p className="text-sm text-muted-foreground">
          Executado por {data.executedBy?.name ?? 'utilizador removido'} em{' '}
          {formatDateTime(data.executedAt)}
          {data.testPlanId && data.testPlanName && (
            <>
              {' '}
              · Plano{' '}
              <Link
                className="hover:underline"
                to={`/projects/${project.id}/tests/plans/${data.testPlanId}`}
              >
                {data.testPlanName}
              </Link>
            </>
          )}
        </p>
        {!data.canEdit && (
          <p className="text-sm text-muted-foreground">
            Consulta apenas: só o executor ou quem gere testes pode alterar.
          </p>
        )}
      </div>
      <TestRunEditForm key={data.version} run={data} />
      <TestRunBugs run={data} />
      <TestRunEvidences run={data} />
      <Button variant="outline" asChild>
        <Link to={`/projects/${project.id}/tests/runs`}>Voltar às execuções</Link>
      </Button>
    </div>
  )
}
