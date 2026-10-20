import { useState } from 'react'
import { Link } from 'react-router'

import { Pagination } from '@/components/Pagination'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
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
import { TestingNav, TestPlanStatusBadge } from '@/features/testing/TestingShared'
import { useTestPlans } from '@/features/testing/useTesting'
import { usePermission } from '@/hooks/usePermissions'
import { formatDateTime } from '@/services/common'
import { testPlanStatusLabels, type TestPlanStatus } from '@/services/testing'

const PAGE_SIZE = 25

export function TestPlansPage() {
  const { project } = useProjectContext()
  const canManage = usePermission('tests:manage') && project.status !== 'archived'
  const [status, setStatus] = useState<TestPlanStatus | ''>('')
  const [page, setPage] = useState(1)
  const plans = useTestPlans({
    projectId: project.id,
    status: status ? [status] : undefined,
    page,
    pageSize: PAGE_SIZE,
  })

  return (
    <div className="space-y-4">
      <TestingNav projectId={project.id} />
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="space-y-1">
          <Label htmlFor="test-plan-status">Estado</Label>
          <NativeSelect
            id="test-plan-status"
            value={status}
            onChange={(event) => {
              setStatus(event.target.value as TestPlanStatus | '')
              setPage(1)
            }}
          >
            <option value="">Todos</option>
            {Object.entries(testPlanStatusLabels).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </NativeSelect>
        </div>
        {canManage && (
          <Button asChild>
            <Link to={`/projects/${project.id}/tests/plans/new`}>Novo plano de teste</Link>
          </Button>
        )}
      </div>

      {plans.isError && (
        <Alert variant="destructive">
          <AlertDescription>Não foi possível carregar os planos de teste.</AlertDescription>
        </Alert>
      )}
      {plans.isPending && <p className="text-muted-foreground">A carregar…</p>}
      {plans.data && plans.data.items.length === 0 && (
        <p className="text-muted-foreground">Nenhum plano de teste encontrado.</p>
      )}
      {plans.data && plans.data.items.length > 0 && (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Nome</TableHead>
                <TableHead>Estado</TableHead>
                <TableHead>Casos</TableHead>
                <TableHead>Descrição</TableHead>
                <TableHead>Atualizado</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {plans.data.items.map((plan) => (
                <TableRow key={plan.id}>
                  <TableCell>
                    <Link
                      className="font-medium hover:underline"
                      to={`/projects/${project.id}/tests/plans/${plan.id}`}
                    >
                      {plan.name}
                    </Link>
                  </TableCell>
                  <TableCell>
                    <TestPlanStatusBadge status={plan.status} />
                  </TableCell>
                  <TableCell>{plan.testCaseCount}</TableCell>
                  <TableCell className="max-w-md truncate" title={plan.description}>
                    {plan.description || '—'}
                  </TableCell>
                  <TableCell>{formatDateTime(plan.updatedAt)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Pagination
            page={plans.data.page}
            pageSize={plans.data.pageSize}
            total={plans.data.total}
            onChange={setPage}
          />
        </>
      )}
    </div>
  )
}
