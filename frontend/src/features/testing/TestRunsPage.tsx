import { useState } from 'react'
import { Link, useSearchParams } from 'react-router'

import { Pagination } from '@/components/Pagination'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useProjectContext } from '@/features/projects/projectContext'
import { TestingNav, TestRunResultBadge } from '@/features/testing/TestingShared'
import { useTestRuns } from '@/features/testing/useTesting'
import { formatDateTime } from '@/services/common'
import { testRunResultLabels, type TestRunResult } from '@/services/testing'

const PAGE_SIZE = 25

export function TestRunsPage() {
  const { project } = useProjectContext()
  const [params] = useSearchParams()
  const testCaseId = params.get('testCaseId') ?? undefined
  const testPlanId = params.get('testPlanId') ?? undefined
  const [result, setResult] = useState<TestRunResult | ''>('')
  const [onlyMine, setOnlyMine] = useState(false)
  const [page, setPage] = useState(1)
  const runs = useTestRuns({
    projectId: project.id,
    testCaseId,
    testPlanId,
    result: result ? [result] : undefined,
    executedBy: onlyMine ? 'me' : undefined,
    page,
    pageSize: PAGE_SIZE,
  })

  return (
    <div className="space-y-4">
      <TestingNav projectId={project.id} />
      <div className="flex flex-wrap items-end gap-4">
        <div className="space-y-1">
          <Label htmlFor="test-run-result">Resultado</Label>
          <NativeSelect
            id="test-run-result"
            value={result}
            onChange={(event) => {
              setResult(event.target.value as TestRunResult | '')
              setPage(1)
            }}
          >
            <option value="">Todos</option>
            {Object.entries(testRunResultLabels).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </NativeSelect>
        </div>
        <label className="flex items-center gap-2 pb-2 text-sm">
          <input
            type="checkbox"
            checked={onlyMine}
            onChange={(event) => {
              setOnlyMine(event.target.checked)
              setPage(1)
            }}
          />
          Só as minhas
        </label>
      </div>
      {(testCaseId || testPlanId) && (
        <p className="text-sm">
          A mostrar só as execuções {testCaseId ? 'do caso' : 'do plano'} selecionado.{' '}
          <Link className="underline" to={`/projects/${project.id}/tests/runs`}>
            Ver todas
          </Link>
        </p>
      )}
      <p className="text-sm text-muted-foreground">
        Para registar uma execução, abra um plano de teste ou um caso de teste e escolha
        “Executar”.
      </p>

      {runs.isError && (
        <Alert variant="destructive">
          <AlertDescription>Não foi possível carregar as execuções.</AlertDescription>
        </Alert>
      )}
      {runs.isPending && <p className="text-muted-foreground">A carregar…</p>}
      {runs.data && runs.data.items.length === 0 && (
        <p className="text-muted-foreground">Nenhuma execução encontrada.</p>
      )}
      {runs.data && runs.data.items.length > 0 && (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Data</TableHead>
                <TableHead>Caso</TableHead>
                <TableHead>Resultado</TableHead>
                <TableHead>Plano</TableHead>
                <TableHead>Ambiente</TableHead>
                <TableHead>Executor</TableHead>
                <TableHead>Bugs</TableHead>
                <TableHead>Evidências</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {runs.data.items.map((run) => (
                <TableRow key={run.id}>
                  <TableCell>
                    <Link
                      className="font-medium hover:underline"
                      to={`/projects/${project.id}/tests/runs/${run.id}`}
                    >
                      {formatDateTime(run.executedAt)}
                    </Link>
                  </TableCell>
                  <TableCell>
                    <span className="font-mono text-xs">{run.testCaseKey}</span> {run.testCaseTitle}
                  </TableCell>
                  <TableCell>
                    <TestRunResultBadge result={run.result} />
                  </TableCell>
                  <TableCell>{run.testPlanName ?? '—'}</TableCell>
                  <TableCell>{run.environment || '—'}</TableCell>
                  <TableCell>{run.executedBy?.name ?? '—'}</TableCell>
                  <TableCell>{run.bugCount}</TableCell>
                  <TableCell>{run.evidenceCount}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Pagination
            page={runs.data.page}
            pageSize={runs.data.pageSize}
            total={runs.data.total}
            onChange={setPage}
          />
        </>
      )}
    </div>
  )
}
