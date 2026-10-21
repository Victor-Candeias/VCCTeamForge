import { NavLink } from 'react-router'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import { IssueStatusBadge } from '@/features/issues/IssueBadges'
import { useIssues } from '@/features/issues/useIssues'
import { cn } from '@/lib/utils'
import type { IssueRef, IssueType } from '@/services/issues'
import {
  testCaseStatusLabels,
  testPlanStatusLabels,
  testRunResultLabels,
  type TestCaseStatus,
  type TestPlanStatus,
  type TestRunResult,
} from '@/services/testing'

export function TestingNav({ projectId }: { projectId: string }) {
  const link = ({ isActive }: { isActive: boolean }) =>
    cn(
      'rounded-md px-3 py-1.5 text-sm font-medium',
      isActive ? 'bg-muted text-foreground' : 'text-muted-foreground hover:text-foreground',
    )
  return (
    <nav aria-label="Testes" className="flex gap-2">
      <NavLink end to={`/projects/${projectId}/tests`} className={link}>
        Casos de teste
      </NavLink>
      <NavLink to={`/projects/${projectId}/tests/plans`} className={link}>
        Planos de teste
      </NavLink>
      <NavLink to={`/projects/${projectId}/tests/runs`} className={link}>
        Execuções
      </NavLink>
    </nav>
  )
}

export function TestCaseStatusBadge({ status }: { status: TestCaseStatus }) {
  return (
    <Badge variant={status === 'ready' ? 'default' : status === 'deprecated' ? 'outline' : 'secondary'}>
      {testCaseStatusLabels[status]}
    </Badge>
  )
}

export function TestPlanStatusBadge({ status }: { status: TestPlanStatus }) {
  return (
    <Badge variant={status === 'active' ? 'default' : status === 'closed' ? 'outline' : 'secondary'}>
      {testPlanStatusLabels[status]}
    </Badge>
  )
}

const resultStyles: Record<TestRunResult, string> = {
  pass: 'border-transparent bg-success text-white',
  fail: 'border-transparent bg-destructive text-white',
  blocked: 'border-transparent bg-warning text-white',
  not_run: '',
  skipped: '',
}

export function TestRunResultBadge({ result }: { result: TestRunResult }) {
  return (
    <Badge
      variant={result === 'not_run' || result === 'skipped' ? 'outline' : 'default'}
      className={resultStyles[result]}
    >
      {testRunResultLabels[result]}
    </Badge>
  )
}

/** Lista de issues ligadas com seletor das issues do projeto (até 100, por número). */
export function IssueLinks({
  projectId,
  value,
  onChange,
  readOnly,
  error,
  id = 'link-issue',
  label = 'Issues ligadas',
  emptyText = 'Nenhuma issue ligada.',
  placeholder = 'Ligar issue…',
  types,
}: {
  projectId: string
  value: IssueRef[]
  onChange: (issues: IssueRef[]) => void
  readOnly: boolean
  error?: string
  id?: string
  label?: string
  emptyText?: string
  placeholder?: string
  types?: IssueType[]
}) {
  const candidates = useIssues({ projectId, type: types, sort: 'number', pageSize: 100 }, !readOnly)
  const selected = new Set(value.map((issue) => issue.id))
  const available = (candidates.data?.items ?? []).filter((issue) => !selected.has(issue.id))

  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      {value.length === 0 ? (
        <p className="text-sm text-muted-foreground">{emptyText}</p>
      ) : (
        <ul className="space-y-1">
          {value.map((issue) => (
            <li key={issue.id} className="flex items-center gap-2 text-sm">
              <span>
                {issue.key} · {issue.title}
              </span>
              <IssueStatusBadge status={issue.status} />
              {!readOnly && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  aria-label={`Remover ${issue.key}`}
                  onClick={() => onChange(value.filter((item) => item.id !== issue.id))}
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
          id={id}
          value=""
          onChange={(event) => {
            const issue = available.find((item) => item.id === event.target.value)
            if (issue) onChange([...value, issue])
          }}
        >
          <option value="">{placeholder}</option>
          {available.map((issue) => (
            <option key={issue.id} value={issue.id}>
              {issue.key} · {issue.title}
            </option>
          ))}
        </NativeSelect>
      )}
      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  )
}
