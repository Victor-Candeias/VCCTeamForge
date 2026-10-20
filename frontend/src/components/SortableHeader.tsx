import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react'

import { TableHead } from '@/components/ui/table'

/** Cabeçalho de coluna ordenável: alterna `campo` ↔ `-campo` e expõe `aria-sort`. */
export function SortableHeader({
  field,
  label,
  sort,
  onSort,
}: {
  field: string
  label: string
  sort: string
  onSort: (sort: string) => void
}) {
  const active = sort.replace(/^-/, '') === field
  const descending = sort.startsWith('-')
  const ariaSort = !active ? 'none' : descending ? 'descending' : 'ascending'
  const Icon = !active ? ArrowUpDown : descending ? ArrowDown : ArrowUp
  return (
    <TableHead aria-sort={ariaSort}>
      <button
        type="button"
        className="inline-flex items-center gap-1 hover:text-foreground"
        onClick={() => onSort(active && !descending ? `-${field}` : field)}
      >
        {label}
        <Icon aria-hidden className="size-3.5" />
      </button>
    </TableHead>
  )
}
