import { useEffect, useState, type ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import { useProjectLabels } from '@/features/issues/useIssues'
import type { IssueFilterName, IssueListFilters } from '@/features/issues/useIssueSearchParams'
import { useProjectMembers } from '@/features/projects/useProjects'
import { priorityLabels } from '@/services/common'
import { issueStatusLabels, issueTypeLabels } from '@/services/issues'

const SEARCH_DEBOUNCE_MS = 300

function SearchInput({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const [text, setText] = useState(value)
  const [lastValue, setLastValue] = useState(value)
  if (value !== lastValue) {
    // O URL mudou por fora (ex.: limpar filtros ou navegação): sincronizar o campo.
    setLastValue(value)
    setText(value)
  }

  useEffect(() => {
    if (text === value) return
    const timer = setTimeout(() => onChange(text), SEARCH_DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [text, value, onChange])

  return (
    <div className="space-y-1">
      <Label htmlFor="issue-search">Pesquisar</Label>
      <Input
        id="issue-search"
        type="search"
        placeholder="Chave ou título"
        maxLength={100}
        value={text}
        onChange={(event) => setText(event.target.value)}
      />
    </div>
  )
}

function FilterSelect({
  id,
  label,
  value,
  onChange,
  children,
}: {
  id: string
  label: string
  value: string
  onChange: (value: string) => void
  children: ReactNode
}) {
  return (
    <div className="space-y-1">
      <Label htmlFor={id}>{label}</Label>
      <NativeSelect id={id} value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">Todos</option>
        {children}
      </NativeSelect>
    </div>
  )
}

function options(labels: Record<string, string>) {
  return Object.entries(labels).map(([value, label]) => (
    <option key={value} value={value}>
      {label}
    </option>
  ))
}

export function IssueFilters({
  projectId,
  filters,
  activeFilters,
  onChange,
  onClear,
}: {
  projectId: string
  filters: IssueListFilters
  activeFilters: number
  onChange: (name: IssueFilterName, value: string | boolean) => void
  onClear: () => void
}) {
  const members = useProjectMembers(projectId)
  const labels = useProjectLabels(projectId)
  const labelOptions = labels.data ?? []

  return (
    <div className="flex flex-wrap items-end gap-3" role="search" aria-label="Filtros de issues">
      <SearchInput value={filters.q} onChange={(value) => onChange('q', value)} />
      <FilterSelect
        id="filter-status"
        label="Estado"
        value={filters.status}
        onChange={(value) => onChange('status', value)}
      >
        {options(issueStatusLabels)}
      </FilterSelect>
      <FilterSelect
        id="filter-priority"
        label="Prioridade"
        value={filters.priority}
        onChange={(value) => onChange('priority', value)}
      >
        {options(priorityLabels)}
      </FilterSelect>
      <FilterSelect
        id="filter-type"
        label="Tipo"
        value={filters.type}
        onChange={(value) => onChange('type', value)}
      >
        {options(issueTypeLabels)}
      </FilterSelect>
      <FilterSelect
        id="filter-assignee"
        label="Responsável"
        value={filters.assigneeId}
        onChange={(value) => onChange('assigneeId', value)}
      >
        <option value="me">Eu</option>
        <option value="none">Sem responsável</option>
        {(members.data?.members ?? []).map((member) => (
          <option key={member.id} value={member.id}>
            {member.name}
          </option>
        ))}
      </FilterSelect>
      <FilterSelect
        id="filter-label"
        label="Label"
        value={filters.label}
        onChange={(value) => onChange('label', value)}
      >
        {filters.label && !labelOptions.includes(filters.label) && (
          <option value={filters.label}>{filters.label}</option>
        )}
        {labelOptions.map((label) => (
          <option key={label} value={label}>
            {label}
          </option>
        ))}
      </FilterSelect>
      <label className="flex items-center gap-2 pb-1.5 text-sm">
        <input
          type="checkbox"
          checked={filters.blocked}
          onChange={(event) => onChange('blocked', event.target.checked)}
        />
        Só bloqueadas
      </label>
      {activeFilters > 0 && (
        <Button variant="ghost" size="sm" onClick={onClear}>
          Limpar filtros ({activeFilters})
        </Button>
      )}
    </div>
  )
}
