import { Button } from '@/components/ui/button'

export function Pagination({
  page,
  pageSize,
  total,
  onChange,
}: {
  page: number
  pageSize: number
  total: number
  onChange: (page: number) => void
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize))
  return (
    <div className="flex items-center justify-between text-sm text-muted-foreground">
      <span>
        {total} resultado{total === 1 ? '' : 's'}
      </span>
      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => onChange(page - 1)}>
          Anterior
        </Button>
        <span>
          Página {page} de {pages}
        </span>
        <Button
          variant="outline"
          size="sm"
          disabled={page >= pages}
          onClick={() => onChange(page + 1)}
        >
          Seguinte
        </Button>
      </div>
    </div>
  )
}
