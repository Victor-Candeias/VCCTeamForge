import { useState } from 'react'
import { Link } from 'react-router'

import { Pagination } from '@/components/Pagination'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
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
import { TestCaseStatusBadge, TestingNav } from '@/features/testing/TestingShared'
import { useTestCases } from '@/features/testing/useTesting'
import { useDebouncedValue } from '@/hooks/useDebouncedValue'
import { usePermission } from '@/hooks/usePermissions'
import { formatDateTime, priorityLabels, type Priority } from '@/services/common'
import { testCaseStatusLabels, type TestCaseStatus } from '@/services/testing'

const PAGE_SIZE = 25

export function TestCasesPage() {
  const { project } = useProjectContext()
  const canManage = usePermission('tests:manage') && project.status !== 'archived'
  const [text, setText] = useState('')
  const [status, setStatus] = useState<TestCaseStatus | ''>('')
  const [priority, setPriority] = useState<Priority | ''>('')
  const [page, setPage] = useState(1)
  const q = useDebouncedValue(text.trim())
  const cases = useTestCases({
    projectId: project.id,
    status: status ? [status] : undefined,
    priority: priority ? [priority] : undefined,
    q: q || undefined,
    page,
    pageSize: PAGE_SIZE,
  })

  return (
    <div className="space-y-4">
      <TestingNav projectId={project.id} />
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-wrap items-end gap-4">
          <div className="space-y-1">
            <Label htmlFor="test-case-search">Pesquisar</Label>
            <Input
              id="test-case-search"
              type="search"
              placeholder="TC-n ou título"
              maxLength={100}
              value={text}
              onChange={(event) => {
                setText(event.target.value)
                setPage(1)
              }}
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="test-case-status">Estado</Label>
            <NativeSelect
              id="test-case-status"
              value={status}
              onChange={(event) => {
                setStatus(event.target.value as TestCaseStatus | '')
                setPage(1)
              }}
            >
              <option value="">Todos</option>
              {Object.entries(testCaseStatusLabels).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </NativeSelect>
          </div>
          <div className="space-y-1">
            <Label htmlFor="test-case-priority">Prioridade</Label>
            <NativeSelect
              id="test-case-priority"
              value={priority}
              onChange={(event) => {
                setPriority(event.target.value as Priority | '')
                setPage(1)
              }}
            >
              <option value="">Todas</option>
              {Object.entries(priorityLabels).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </NativeSelect>
          </div>
        </div>
        {canManage && (
          <Button asChild>
            <Link to={`/projects/${project.id}/tests/cases/new`}>Novo caso de teste</Link>
          </Button>
        )}
      </div>

      {cases.isError && (
        <Alert variant="destructive">
          <AlertDescription>Não foi possível carregar os casos de teste.</AlertDescription>
        </Alert>
      )}
      {cases.isPending && <p className="text-muted-foreground">A carregar…</p>}
      {cases.data && cases.data.items.length === 0 && (
        <p className="text-muted-foreground">Nenhum caso de teste encontrado.</p>
      )}
      {cases.data && cases.data.items.length > 0 && (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-24">Chave</TableHead>
                <TableHead>Título</TableHead>
                <TableHead>Estado</TableHead>
                <TableHead>Prioridade</TableHead>
                <TableHead>Passos</TableHead>
                <TableHead>Labels</TableHead>
                <TableHead>Atualizado</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {cases.data.items.map((testCase) => (
                <TableRow key={testCase.id}>
                  <TableCell className="font-mono text-xs">{testCase.key}</TableCell>
                  <TableCell>
                    <Link
                      className="font-medium hover:underline"
                      to={`/projects/${project.id}/tests/cases/${testCase.id}`}
                    >
                      {testCase.title}
                    </Link>
                  </TableCell>
                  <TableCell>
                    <TestCaseStatusBadge status={testCase.status} />
                  </TableCell>
                  <TableCell>{priorityLabels[testCase.priority]}</TableCell>
                  <TableCell>{testCase.stepCount}</TableCell>
                  <TableCell>{testCase.labels.join(', ') || '—'}</TableCell>
                  <TableCell>{formatDateTime(testCase.updatedAt)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Pagination
            page={cases.data.page}
            pageSize={cases.data.pageSize}
            total={cases.data.total}
            onChange={setPage}
          />
        </>
      )}
    </div>
  )
}
