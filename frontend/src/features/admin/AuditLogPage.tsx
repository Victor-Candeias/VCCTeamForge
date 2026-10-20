import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { Pagination } from '@/components/Pagination'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { usePermission } from '@/hooks/usePermissions'
import { DEFAULT_PAGE_SIZE } from '@/lib/pagination'
import { listAuditLogs, type AuditFilters } from '@/services/audit'
import { formatDateTime } from '@/services/common'

type FilterKey = 'action' | 'entityType' | 'from' | 'to'

const filterFields: { key: FilterKey; label: string; type: string; placeholder?: string }[] = [
  { key: 'action', label: 'Ação', type: 'text', placeholder: 'ex.: issue.updated' },
  { key: 'entityType', label: 'Entidade', type: 'text', placeholder: 'ex.: issue' },
  { key: 'from', label: 'Desde', type: 'date' },
  { key: 'to', label: 'Até', type: 'date' },
]

function summarizeDetails(details: Record<string, unknown>): string {
  const parts: string[] = []
  if (typeof details.issueKey === 'string') parts.push(details.issueKey)
  if (Array.isArray(details.changes) && details.changes.length > 0) {
    const fields = details.changes
      .map((change) => (change as { field?: unknown }).field)
      .filter((field): field is string => typeof field === 'string')
    if (fields.length > 0) parts.push(`campos: ${fields.join(', ')}`)
  }
  if (typeof details.reason === 'string') parts.push(details.reason)
  return parts.join(' · ') || '—'
}

export function AuditLogPage() {
  const canRead = usePermission('audit:read')
  const [filters, setFilters] = useState<Partial<Record<FilterKey, string>>>({})
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE)
  const query: AuditFilters = {
    ...Object.fromEntries(Object.entries(filters).map(([key, value]) => [key, value?.trim()])),
    page,
    pageSize,
  }
  const logs = useQuery({
    queryKey: ['audit-logs', query],
    queryFn: () => listAuditLogs(query),
    placeholderData: keepPreviousData,
    enabled: canRead,
  })

  if (!canRead) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Não tem permissão para consultar a auditoria.</AlertDescription>
      </Alert>
    )
  }

  const setFilter = (key: FilterKey, value: string) => {
    setFilters((current) => ({ ...current, [key]: value }))
    setPage(1)
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Auditoria</h1>
      <div className="flex flex-wrap items-end gap-3">
        {filterFields.map((field) => (
          <div key={field.key} className="space-y-1">
            <Label htmlFor={`audit-${field.key}`}>{field.label}</Label>
            <Input
              id={`audit-${field.key}`}
              type={field.type}
              placeholder={field.placeholder}
              className="w-48"
              value={filters[field.key] ?? ''}
              onChange={(event) => setFilter(field.key, event.target.value)}
            />
          </div>
        ))}
        {Object.values(filters).some(Boolean) && (
          <Button
            variant="ghost"
            onClick={() => {
              setFilters({})
              setPage(1)
            }}
          >
            Limpar filtros
          </Button>
        )}
      </div>
      {logs.isError && (
        <Alert variant="destructive">
          <AlertDescription>Não foi possível carregar os registos de auditoria.</AlertDescription>
        </Alert>
      )}
      {logs.isPending && <p className="text-muted-foreground">A carregar…</p>}
      {logs.data && (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Data</TableHead>
                <TableHead>Utilizador</TableHead>
                <TableHead>Ação</TableHead>
                <TableHead>Entidade</TableHead>
                <TableHead>Detalhes</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {logs.data.items.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="text-center text-muted-foreground">
                    Sem registos.
                  </TableCell>
                </TableRow>
              )}
              {logs.data.items.map((log) => (
                <TableRow key={log.id}>
                  <TableCell className="whitespace-nowrap">{formatDateTime(log.createdAt)}</TableCell>
                  <TableCell>{log.actor?.name ?? '—'}</TableCell>
                  <TableCell className="font-mono text-xs">{log.action}</TableCell>
                  <TableCell>
                    {log.entityType ?? '—'}
                    {log.entityId && (
                      <span className="block font-mono text-xs text-muted-foreground">
                        {log.entityId}
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="text-sm">{summarizeDetails(log.details)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Pagination
            page={logs.data.page}
            pageSize={logs.data.pageSize}
            total={logs.data.total}
            onChange={setPage}
            onPageSizeChange={(size) => {
              setPageSize(size)
              setPage(1)
            }}
          />
        </>
      )}
    </div>
  )
}
