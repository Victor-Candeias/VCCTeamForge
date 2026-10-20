import { useSearchParams } from 'react-router'

import { DEFAULT_PAGE_SIZE, PAGE_SIZE_OPTIONS } from '@/lib/pagination'
import type { Priority } from '@/services/common'
import {
  issueSortFields,
  issueStatuses,
  issueTypes,
  type IssueSearchParams,
  type IssueStatus,
  type IssueType,
} from '@/services/issues'

const priorities: Priority[] = ['low', 'medium', 'high', 'critical']
export const DEFAULT_ISSUE_SORT = '-number'

/** Filtros da lista de issues guardados no URL (partilháveis e com histórico). */
export type IssueListFilters = {
  status: IssueStatus | ''
  priority: Priority | ''
  type: IssueType | ''
  assigneeId: string
  label: string
  blocked: boolean
  q: string
}

export type IssueFilterName = keyof IssueListFilters

function oneOf<T extends string>(value: string | null, allowed: readonly T[]): T | '' {
  return value !== null && (allowed as readonly string[]).includes(value) ? (value as T) : ''
}

function positiveInt(value: string | null, fallback: number) {
  const parsed = Number(value)
  return Number.isInteger(parsed) && parsed >= 1 ? parsed : fallback
}

function validSort(value: string | null) {
  if (!value) return DEFAULT_ISSUE_SORT
  const field = value.replace(/^-/, '')
  return (issueSortFields as readonly string[]).includes(field) ? value : DEFAULT_ISSUE_SORT
}

export function useIssueSearchParams(projectId: string) {
  const [searchParams, setSearchParams] = useSearchParams()

  const filters: IssueListFilters = {
    status: oneOf(searchParams.get('status'), issueStatuses),
    priority: oneOf(searchParams.get('priority'), priorities),
    type: oneOf(searchParams.get('type'), issueTypes),
    assigneeId: searchParams.get('assigneeId') ?? '',
    label: searchParams.get('label') ?? '',
    blocked: searchParams.get('blocked') === 'true',
    q: searchParams.get('q') ?? '',
  }
  const sort = validSort(searchParams.get('sort'))
  const page = positiveInt(searchParams.get('page'), 1)
  const pageSizeParam = positiveInt(searchParams.get('pageSize'), DEFAULT_PAGE_SIZE)
  const pageSize = PAGE_SIZE_OPTIONS.includes(pageSizeParam) ? pageSizeParam : DEFAULT_PAGE_SIZE

  const params: IssueSearchParams = {
    projectId,
    status: filters.status ? [filters.status] : undefined,
    priority: filters.priority ? [filters.priority] : undefined,
    type: filters.type ? [filters.type] : undefined,
    assigneeId: filters.assigneeId ? [filters.assigneeId] : undefined,
    label: filters.label ? [filters.label] : undefined,
    blocked: filters.blocked || undefined,
    q: filters.q.trim() || undefined,
    sort: sort === DEFAULT_ISSUE_SORT ? undefined : sort,
    page,
    pageSize,
  }

  /** Altera parâmetros do URL; mudar filtros, ordenação ou tamanho volta à primeira página. */
  const update = (changes: Record<string, string | number | boolean | undefined>) => {
    setSearchParams(
      (current) => {
        const next = new URLSearchParams(current)
        for (const [name, value] of Object.entries(changes)) {
          if (value === undefined || value === '' || value === false) next.delete(name)
          else next.set(name, String(value))
        }
        if (!('page' in changes)) next.delete('page')
        return next
      },
      { replace: 'q' in changes },
    )
  }

  const activeFilters = Object.entries(filters).filter(([, value]) => Boolean(value)).length

  return {
    filters,
    params,
    sort,
    page,
    pageSize,
    activeFilters,
    setFilter: (name: IssueFilterName, value: string | boolean) => update({ [name]: value }),
    clearFilters: () =>
      update(Object.fromEntries(Object.keys(filters).map((name) => [name, undefined]))),
    setSort: (value: string) =>
      update({ sort: value === DEFAULT_ISSUE_SORT ? undefined : value }),
    setPage: (value: number) => update({ page: value === 1 ? undefined : value }),
    setPageSize: (value: number) =>
      update({ pageSize: value === DEFAULT_PAGE_SIZE ? undefined : value }),
  }
}
