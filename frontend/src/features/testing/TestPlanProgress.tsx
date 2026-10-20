import { Link } from 'react-router'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { TestRunResultBadge } from '@/features/testing/TestingShared'
import { useTestPlanProgress } from '@/features/testing/useTesting'
import { formatDateTime } from '@/services/common'
import {
  formatPassRate,
  testRunResultLabels,
  type TestPlan,
  type TestRunResult,
} from '@/services/testing'

const SUMMARY_RESULTS: TestRunResult[] = ['pass', 'fail', 'blocked', 'skipped', 'not_run']

/** Último resultado de cada caso do plano, pass rate e regressões (pass → fail). */
export function TestPlanProgress({
  plan,
  projectId,
  canExecute,
}: {
  plan: TestPlan
  projectId: string
  canExecute: boolean
}) {
  const progress = useTestPlanProgress(plan.id)
  const runnable = canExecute && plan.status !== 'closed'

  return (
    <section aria-labelledby="plan-progress" className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id="plan-progress" className="font-medium">
          Progresso da execução
        </h3>
        <Link
          className="text-sm hover:underline"
          to={`/projects/${projectId}/tests/runs?testPlanId=${plan.id}`}
        >
          Histórico de execuções
        </Link>
      </div>
      {progress.isError && (
        <Alert variant="destructive">
          <AlertDescription>Não foi possível carregar o progresso do plano.</AlertDescription>
        </Alert>
      )}
      {progress.isPending && <p className="text-sm text-muted-foreground">A carregar…</p>}
      {progress.data && (
        <>
          <dl className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
            <div>
              <dt className="inline text-muted-foreground">Executados: </dt>
              <dd className="inline font-medium">
                {progress.data.executedCases}/{progress.data.totalCases}
              </dd>
            </div>
            <div>
              <dt className="inline text-muted-foreground">Pass rate: </dt>
              <dd className="inline font-medium">{formatPassRate(progress.data.passRate)}</dd>
            </div>
            <div>
              <dt className="inline text-muted-foreground">Regressões: </dt>
              <dd className="inline font-medium">{progress.data.regressions}</dd>
            </div>
            {SUMMARY_RESULTS.map((result) => (
              <div key={result}>
                <dt className="inline text-muted-foreground">{testRunResultLabels[result]}: </dt>
                <dd className="inline font-medium">{progress.data.counts[result] ?? 0}</dd>
              </div>
            ))}
          </dl>
          {progress.data.cases.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Caso</TableHead>
                  <TableHead>Último resultado</TableHead>
                  <TableHead>Executado</TableHead>
                  <TableHead>
                    <span className="sr-only">Ações</span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {progress.data.cases.map((item) => (
                  <TableRow key={item.testCase.id}>
                    <TableCell>
                      <span className="font-mono text-xs">{item.testCase.key}</span>{' '}
                      {item.testCase.title}
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap items-center gap-2">
                        {item.lastRunId ? (
                          <Link to={`/projects/${projectId}/tests/runs/${item.lastRunId}`}>
                            <TestRunResultBadge result={item.lastResult} />
                          </Link>
                        ) : (
                          <TestRunResultBadge result={item.lastResult} />
                        )}
                        {item.regression && (
                          <span className="text-xs font-medium text-destructive">Regressão</span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-sm">
                      {item.lastExecutedAt
                        ? `${formatDateTime(item.lastExecutedAt)} · ${item.lastExecutedBy?.name ?? '—'}`
                        : '—'}
                    </TableCell>
                    <TableCell className="text-right">
                      {runnable && item.testCase.status !== 'deprecated' && (
                        <Button size="sm" variant="outline" asChild>
                          <Link
                            aria-label={`Executar ${item.testCase.key}`}
                            to={`/projects/${projectId}/tests/runs/new?testCaseId=${item.testCase.id}&testPlanId=${plan.id}`}
                          >
                            Executar
                          </Link>
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </>
      )}
    </section>
  )
}
